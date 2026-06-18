from __future__ import annotations

from pathlib import Path
import re
import wave

import numpy as np


def export_wav(stereo_xy: np.ndarray, out_path: str | Path, sample_rate: int) -> None:
    """Write a stereo float array in [-1, 1] as PCM 16-bit WAV."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    clipped = np.clip(stereo_xy, -1.0, 1.0)
    pcm = np.round(clipped * 32767.0).astype("<i2")
    with wave.open(str(out_path), "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm.tobytes())


def note_to_frequency(note: str) -> float:
    """Convert scientific pitch notation like C2, F#3, Bb1 to Hz using A4=440."""
    match = re.fullmatch(r"\s*([A-Ga-g])([#b]?)(-?\d+)\s*", note)
    if not match:
        raise ValueError(f"Invalid note name: {note!r}. Use names like C2, F#2, Bb1.")
    name, accidental, octave_text = match.groups()
    semitones = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
    pitch_class = semitones[name.upper()]
    if accidental == "#":
        pitch_class += 1
    elif accidental == "b":
        pitch_class -= 1
    octave = int(octave_text)
    midi_note = (octave + 1) * 12 + pitch_class
    return 440.0 * (2.0 ** ((midi_note - 69) / 12.0))
