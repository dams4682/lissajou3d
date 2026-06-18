from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np

from xy_audio.engine import export_wav, note_to_frequency
from .geometry import Transform, Wireframe, make_shape, project_wireframe
from .motion import MotionTrack


@dataclass(slots=True)
class Render3DConfig:
    shape: str = "cube"
    duration: float = 5.0
    sample_rate: int = 48_000
    scan_rate_hz: float | None = 40.0
    scan_note: str | None = None
    scale: float = 0.9
    smoothing: int = 1
    normalize: bool = True
    invert_x: bool = False
    invert_y: bool = True
    projection: str = "orthographic"
    perspective: float = 2.8
    view_scale: float = 2.4
    sphere_detail: int = 16
    auto_rotate_degrees: float = 360.0


def build_3d_xy_audio(
    config: Render3DConfig,
    motion: MotionTrack | None = None,
    wireframe: Wireframe | None = None,
) -> np.ndarray:
    if config.duration <= 0:
        raise ValueError("Duration must be greater than zero.")
    if config.sample_rate <= 0:
        raise ValueError("Sample rate must be greater than zero.")
    if config.scale <= 0:
        raise ValueError("Scale must be greater than zero.")

    wireframe = wireframe or make_shape(config.shape, detail=config.sphere_detail)
    total_samples = max(2, int(round(config.duration * config.sample_rate)))
    cycles = max(1, int(round(_scan_rate(config) * config.duration)))
    base_samples = max(2, total_samples // cycles)
    chunks: list[np.ndarray] = []

    for cycle in range(cycles):
        center_t = (cycle + 0.5) / cycles * config.duration
        transform = _transform_at(center_t, config, motion)
        contours = project_wireframe(
            wireframe,
            transform,
            projection=config.projection,
            perspective=config.perspective,
            view_scale=config.view_scale,
        )
        trajectory = _contours_to_trajectory(contours)
        chunks.append(_resample_polyline(trajectory, base_samples))

    audio = np.vstack(chunks)
    if len(audio) < total_samples:
        audio = np.vstack((audio, audio[-1:].repeat(total_samples - len(audio), axis=0)))
    audio = audio[:total_samples]

    if config.smoothing > 1:
        audio = _smooth(audio, config.smoothing)
    audio = _fit_to_unit(audio) * float(config.scale)

    if config.normalize:
        max_abs = float(np.max(np.abs(audio)))
        if max_abs > 0:
            audio = audio / max_abs * min(float(config.scale), 1.0)

    if config.invert_x:
        audio[:, 0] *= -1.0
    if config.invert_y:
        audio[:, 1] *= -1.0

    return np.clip(audio, -1.0, 1.0).astype(np.float32)


def export_3d_wav(out_path: str, config: Render3DConfig, motion: MotionTrack | None = None) -> None:
    export_wav(build_3d_xy_audio(config, motion=motion), out_path, config.sample_rate)


def _scan_rate(config: Render3DConfig) -> float:
    if config.scan_note:
        return note_to_frequency(config.scan_note)
    if config.scan_rate_hz and config.scan_rate_hz > 0:
        return float(config.scan_rate_hz)
    return 40.0


def _transform_at(time_seconds: float, config: Render3DConfig, motion: MotionTrack | None) -> Transform:
    if motion and motion.keyframes and motion.duration > 0:
        src_t = min(time_seconds, motion.duration)
        return motion.sample(src_t)
    amount = time_seconds / max(1e-9, config.duration)
    return Transform(
        rotation_x=25.0 + amount * config.auto_rotate_degrees * 0.37,
        rotation_y=amount * config.auto_rotate_degrees,
        rotation_z=amount * config.auto_rotate_degrees * 0.19,
        zoom=1.0,
    )


def _contours_to_trajectory(contours: list[np.ndarray]) -> np.ndarray:
    if not contours:
        return np.zeros((2, 2), dtype=np.float64)
    pieces: list[np.ndarray] = []
    previous: np.ndarray | None = None
    for contour in contours:
        if previous is not None:
            pieces.append(np.linspace(previous, contour[0], 4, dtype=np.float64)[1:-1])
        pieces.append(contour)
        previous = contour[-1]
    return np.vstack(pieces)


def _resample_polyline(points: np.ndarray, target_samples: int) -> np.ndarray:
    if len(points) < 2:
        return np.repeat(points[:1], target_samples, axis=0)
    deltas = np.diff(points, axis=0)
    distances = np.linalg.norm(deltas, axis=1)
    cumulative = np.concatenate(([0.0], np.cumsum(distances)))
    total = float(cumulative[-1])
    if total <= 0:
        return np.repeat(points[:1], target_samples, axis=0)
    desired = np.linspace(0.0, total, target_samples)
    x = np.interp(desired, cumulative, points[:, 0])
    y = np.interp(desired, cumulative, points[:, 1])
    return np.column_stack((x, y))


def _fit_to_unit(points: np.ndarray) -> np.ndarray:
    centered = np.asarray(points, dtype=np.float64).copy()
    mins = np.min(centered, axis=0)
    maxs = np.max(centered, axis=0)
    centered -= (mins + maxs) / 2.0
    span = max(float(maxs[0] - mins[0]), float(maxs[1] - mins[1]))
    if span > 0:
        centered /= span / 2.0
    return centered


def _smooth(points: np.ndarray, window: int) -> np.ndarray:
    window = max(1, int(window))
    if window <= 1:
        return points
    if window % 2 == 0:
        window += 1
    kernel = np.ones(window, dtype=np.float64) / window
    smoothed = np.empty_like(points, dtype=np.float64)
    for channel in range(2):
        padded = np.pad(points[:, channel], (window // 2, window // 2), mode="edge")
        smoothed[:, channel] = np.convolve(padded, kernel, mode="valid")
    return smoothed
