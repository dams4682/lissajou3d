from __future__ import annotations

import math
import tempfile
from pathlib import Path
import wave

import numpy as np

from .engine import export_wav, note_to_frequency


def sine_note(note: str, duration: float = 1.0, sample_rate: int = 48_000, gain: float = 0.25) -> np.ndarray:
    frequency = note_to_frequency(note)
    samples = max(2, int(round(duration * sample_rate)))
    t = np.arange(samples, dtype=np.float64) / sample_rate
    envelope = _fade_envelope(samples, sample_rate)
    tone = np.sin(2.0 * math.pi * frequency * t) * envelope * gain
    return np.column_stack((tone, tone)).astype(np.float32)


def write_temp_wav(stereo_audio: np.ndarray, sample_rate: int, prefix: str = "xy_audio_") -> Path:
    handle = tempfile.NamedTemporaryFile(prefix=prefix, suffix=".wav", delete=False)
    path = Path(handle.name)
    handle.close()
    export_wav(stereo_audio, path, sample_rate)
    return path


def write_sine_note_wav(note: str, duration: float = 1.0, sample_rate: int = 48_000) -> Path:
    return write_temp_wav(sine_note(note, duration=duration, sample_rate=sample_rate), sample_rate, prefix="xy_note_")


def read_wav_info(path: str | Path) -> tuple[int, int, int]:
    with wave.open(str(path), "rb") as wav:
        return wav.getnchannels(), wav.getframerate(), wav.getnframes()


def _fade_envelope(samples: int, sample_rate: int) -> np.ndarray:
    envelope = np.ones(samples, dtype=np.float64)
    fade_samples = min(samples // 2, max(1, int(sample_rate * 0.015)))
    fade = np.linspace(0.0, 1.0, fade_samples)
    envelope[:fade_samples] *= fade
    envelope[-fade_samples:] *= fade[::-1]
    return envelope
