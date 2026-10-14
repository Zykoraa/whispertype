"""Acoustic noise suppression pipeline."""

import time
from typing import Optional
import numpy as np

try:
    import noisereduce as nr
    HAS_NOISEREDUCE = True
except ImportError:
    HAS_NOISEREDUCE = False


class NoiseSuppressor:
    def __init__(self, enabled: bool = True, prop_decrease: float = 0.75):
        self.enabled = enabled and HAS_NOISEREDUCE
        self.prop_decrease = max(0.0, min(1.0, prop_decrease))

    def process(self, audio: np.ndarray, sample_rate: int = 16000) -> np.ndarray:
        if not self.enabled or audio is None or len(audio) < 512:
            return audio

        try:
            t0 = time.perf_counter()
            cleaned = nr.reduce_noise(
                y=audio,
                sr=sample_rate,
                stationary=True,
                prop_decrease=self.prop_decrease,
                n_fft=512,
            )
            t1 = time.perf_counter()
            return cleaned.astype(np.float32)
        except Exception as e:
            print(f"[WhisperType] Noise suppression warning: {e}")
            return audio
