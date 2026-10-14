"""Speculative background pre-transcription worker for low-latency long utterances."""

import threading
import time
from typing import Optional, Tuple
import numpy as np


class SpeculativeWorker:
    def __init__(self, engine, threshold_sec: float = 2.5, chunk_sec: float = 2.0):
        self.engine = engine
        self.threshold_sec = threshold_sec
        self.chunk_sec = chunk_sec
        self._thread: Optional[threading.Thread] = None
        self._cached_text: Optional[str] = None
        self._cached_sample_count: int = 0
        self._lock = threading.Lock()
        self._is_active = False

    def reset(self):
        with self._lock:
            self._cached_text = None
            self._cached_sample_count = 0
            self._is_active = True

    def pretranscribe(self, snapshot_audio: np.ndarray, sample_rate: int = 16000):
        if snapshot_audio is None:
            return

        chunk_samples = int(self.chunk_sec * sample_rate)
        with self._lock:
            if not self._is_active or self._cached_sample_count > 0:
                return
            if len(snapshot_audio) < chunk_samples:
                return
            self._cached_sample_count = chunk_samples

        def _worker():
            slice_audio = snapshot_audio[:chunk_samples]
            try:
                text = self.engine.transcribe(slice_audio)
                with self._lock:
                    if self._is_active:
                        self._cached_text = text
            except Exception as e:
                print(f"[WhisperType] Speculative pretranscription note: {e}")

        self._thread = threading.Thread(target=_worker, daemon=True)
        self._thread.start()

    def get_result(self, full_audio: np.ndarray, sample_rate: int = 16000) -> Tuple[Optional[str], Optional[np.ndarray]]:
        """Return (cached_prefix_text, remaining_tail_audio) or (None, full_audio)."""
        with self._lock:
            self._is_active = False
            cached_text = self._cached_text
            split_idx = self._cached_sample_count

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=0.1)
            with self._lock:
                cached_text = self._cached_text

        if cached_text and split_idx > 0 and len(full_audio) > split_idx:
            tail_audio = full_audio[split_idx:]
            return cached_text, tail_audio

        return None, full_audio
