"""Auditory feedback cues for start/stop dictation."""

import math
import numpy as np
import sounddevice as sd
from typing import Optional


class AudioFeedback:
    def __init__(self, enabled: bool = True, volume: float = 0.25, sample_rate: int = 44100):
        self.enabled = enabled
        self.volume = max(0.0, min(1.0, volume))
        self.sample_rate = sample_rate
        self._start_cue = self._generate_tone(freq=880.0, duration_ms=25.0, gain=self.volume)
        self._stop_cue = self._generate_tone(freq=520.0, duration_ms=30.0, gain=self.volume)
        self._success_cue = self._generate_success_chime(gain=self.volume)

    def _generate_tone(self, freq: float, duration_ms: float, gain: float) -> np.ndarray:
        num_samples = int(self.sample_rate * (duration_ms / 1000.0))
        t = np.linspace(0, duration_ms / 1000.0, num_samples, endpoint=False)
        # Smooth hanning/tukey window to prevent clicks
        window = np.sin(np.pi * np.linspace(0, 1, num_samples)) ** 2
        tone = gain * np.sin(2.0 * np.pi * freq * t) * window
        return tone.astype(np.float32)

    def _generate_success_chime(self, gain: float) -> np.ndarray:
        # Subtle dual-tone ascending chirp: 700Hz -> 1050Hz
        d1 = int(self.sample_rate * 0.02)
        d2 = int(self.sample_rate * 0.025)
        t1 = np.linspace(0, 0.02, d1, endpoint=False)
        t2 = np.linspace(0, 0.025, d2, endpoint=False)
        w1 = np.sin(np.pi * np.linspace(0, 1, d1)) ** 2
        w2 = np.sin(np.pi * np.linspace(0, 1, d2)) ** 2
        tone1 = (gain * 0.8) * np.sin(2.0 * np.pi * 784.0 * t1) * w1
        tone2 = (gain * 0.8) * np.sin(2.0 * np.pi * 1174.0 * t2) * w2
        return np.concatenate([tone1, tone2]).astype(np.float32)

    def play_start(self):
        if not self.enabled:
            return
        try:
            sd.play(self._start_cue, samplerate=self.sample_rate, blocking=False)
        except Exception:
            pass

    def play_stop(self):
        if not self.enabled:
            return
        try:
            sd.play(self._stop_cue, samplerate=self.sample_rate, blocking=False)
        except Exception:
            pass

    def play_success(self):
        if not self.enabled:
            return
        try:
            sd.play(self._success_cue, samplerate=self.sample_rate, blocking=False)
        except Exception:
            pass
