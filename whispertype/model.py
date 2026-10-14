"""faster-whisper CUDA FP16 inference engine."""

import ctypes
import glob
import os
from pathlib import Path
import sys
import time
from typing import Optional
import numpy as np


def _preload_cuda_libraries():
    """Dynamically preload CUDA runtime libraries from virtualenv site-packages."""
    try:
        venv_root = Path(sys.executable).parent.parent
        site_packages = list(venv_root.glob("lib/python*/site-packages"))
        if not site_packages:
            return
        sp = site_packages[0]

        nvidia_lib_dirs = [
            sp / "nvidia" / "cudnn" / "lib",
            sp / "nvidia" / "cublas" / "lib",
            sp / "nvidia" / "cuda_nvrtc" / "lib",
        ]

        # Update LD_LIBRARY_PATH in process environment
        existing_ld = os.environ.get("LD_LIBRARY_PATH", "")
        new_paths = [str(p) for p in nvidia_lib_dirs if p.exists()]
        if new_paths:
            os.environ["LD_LIBRARY_PATH"] = ":".join(new_paths) + (":" + existing_ld if existing_ld else "")

        # Explicitly dlopen libraries in dependency order
        for lib_dir in nvidia_lib_dirs:
            if not lib_dir.exists():
                continue
            for so_file in sorted(lib_dir.glob("*.so*")):
                try:
                    ctypes.CDLL(str(so_file), mode=ctypes.RTLD_GLOBAL)
                except Exception:
                    pass
    except Exception as e:
        print(f"[WhisperType] Note: CUDA library preloader: {e}")


# Run preloading before importing faster_whisper / ctranslate2
_preload_cuda_libraries()

from faster_whisper import WhisperModel
from whispertype.cleaner import clean_transcript, FILLER_TOKEN_IDS


def _resolve_model_path(model_name: str) -> str:
    """Check local huggingface cache first to avoid unnecessary network calls."""
    hf_cache = Path.home() / ".cache" / "huggingface" / "hub"
    repo_format = f"models--Systran--faster-whisper-{model_name}"
    candidate_dir = hf_cache / repo_format / "snapshots"
    if candidate_dir.exists():
        snapshots = list(candidate_dir.iterdir())
        if snapshots:
            return str(snapshots[0])
    return model_name


class WhisperEngine:
    def __init__(
        self,
        model_name: str = "large-v3-turbo",
        device: str = "cuda",
        compute_type: str = "float16",
        beam_size: int = 2,
        language: str = "en",
        initial_prompt: str = "",
        strip_fillers: bool = True,
    ):
        self.model_name = model_name
        self.device = device
        self.compute_type = compute_type
        self.beam_size = beam_size
        self.language = language
        self.initial_prompt = initial_prompt
        self.strip_fillers = strip_fillers
        self.model_path = _resolve_model_path(model_name)
        # Suppress non-speech special characters; do not suppress raw BPE subwords to avoid mangling valid words like 'error'
        self.suppress_tokens = [-1]

        print(f"[WhisperType] Loading model '{model_name}' on {device} ({compute_type})...")
        t0 = time.perf_counter()
        self.model = WhisperModel(
            self.model_path,
            device=self.device,
            compute_type=self.compute_type,
            local_files_only=Path(self.model_path).is_dir(),
        )
        t1 = time.perf_counter()
        print(f"[WhisperType] Model loaded in {(t1 - t0)*1000:.1f} ms")

        # Warmup engine to compile CUDA kernels and allocate VRAM
        self._warmup()

    def _warmup(self):
        try:
            dummy = np.zeros(16000, dtype=np.float32)
            segments, _ = self.model.transcribe(
                dummy,
                beam_size=1,
                language=self.language,
                vad_filter=False,
            )
            list(segments)
            print("[WhisperType] CUDA warmup complete.")
        except Exception as e:
            print(f"[WhisperType] Warmup warning: {e}")

    def transcribe(
        self,
        audio: np.ndarray,
        initial_prompt: Optional[str] = None,
        strip_fillers: Optional[bool] = None,
    ) -> Optional[str]:
        """Transcribe a 1D float32 audio array and return the clean text."""
        if audio is None or len(audio) == 0:
            return None

        # Check for absolute silence
        rms = np.sqrt(np.mean(np.square(audio)))
        if rms < 0.001:
            return None

        prompt = initial_prompt if initial_prompt is not None else self.initial_prompt
        do_strip = strip_fillers if strip_fillers is not None else self.strip_fillers

        t0 = time.perf_counter()
        segments, info = self.model.transcribe(
            audio,
            beam_size=self.beam_size,
            language=self.language,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=150),
            initial_prompt=prompt if prompt else None,
            suppress_tokens=self.suppress_tokens,
        )

        texts = [s.text.strip() for s in segments if s.text.strip()]
        t1 = time.perf_counter()

        if not texts:
            return None

        raw_text = " ".join(texts).strip()

        # Clean speech disfluencies, stuttering, and filler sounds (preserving all valid words)
        full_text = clean_transcript(
            raw_text,
            strip_fillers=do_strip,
        )

        if not full_text:
            return None

        # Filter out common Whisper hallucination triggers on low-volume background noise
        hallucinations = {
            "thank you.",
            "thank you very much.",
            "thanks for watching.",
            "you",
            "bye.",
            "subscribe",
        }
        if full_text.lower().strip(".!?,") in hallucinations:
            return None

        duration_sec = len(audio) / 16000.0
        elapsed_ms = (t1 - t0) * 1000.0
        print(f"[WhisperType] Transcribed {duration_sec:.2f}s audio in {elapsed_ms:.1f} ms: \"{full_text}\" (raw: \"{raw_text}\")")

        return full_text
