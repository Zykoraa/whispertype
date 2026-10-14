"""In-memory low-latency audio capture via PipeWire."""

import threading
import time
from typing import List, Optional
import numpy as np
import sounddevice as sd


class AudioRecorder:
    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1,
        on_threshold_reached=None,
        threshold_seconds: float = 2.5,
    ):
        self.sample_rate = sample_rate
        self.channels = channels
        self.on_threshold_reached = on_threshold_reached
        self.threshold_samples = int(threshold_seconds * sample_rate)
        self._chunks: List[np.ndarray] = []
        self._total_samples = 0
        self._threshold_fired = False
        self._lock = threading.Lock()
        self._is_recording = False
        self._stream: Optional[sd.InputStream] = None
        self._start_time: float = 0.0

    def _audio_callback(self, indata: np.ndarray, frames: int, time_info, status):
        if status:
            pass
        if self._is_recording:
            should_fire = False
            snapshot = None
            with self._lock:
                self._chunks.append(indata.copy())
                self._total_samples += frames
                if (
                    self.on_threshold_reached
                    and not self._threshold_fired
                    and self._total_samples >= self.threshold_samples
                ):
                    self._threshold_fired = True
                    should_fire = True
                    snapshot = np.concatenate(self._chunks, axis=0).flatten()

            if should_fire and snapshot is not None:
                threading.Thread(
                    target=self.on_threshold_reached,
                    args=(snapshot,),
                    daemon=True,
                ).start()

    def start(self):
        with self._lock:
            self._chunks.clear()
            self._total_samples = 0
            self._threshold_fired = False
            self._is_recording = True
            self._start_time = time.perf_counter()

        if self._stream is None:
            self._stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype="float32",
                blocksize=512,
                callback=self._audio_callback,
            )
            self._stream.start()
        elif not self._stream.active:
            self._stream.start()

    def stop(self) -> Optional[np.ndarray]:
        with self._lock:
            self._is_recording = False
            duration = time.perf_counter() - self._start_time
            chunks = list(self._chunks)
            self._chunks.clear()

        if self._stream and self._stream.active:
            self._stream.stop()

        # Ignore tiny clicks under 120 ms
        if duration < 0.12 or not chunks:
            return None

        # Concatenate chunks into 1D float32 array
        audio = np.concatenate(chunks, axis=0).flatten()
        return audio

    def close(self):
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None
