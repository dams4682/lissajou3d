from __future__ import annotations

from dataclasses import dataclass
import time

from .geometry import Transform


@dataclass(slots=True)
class MotionKeyframe:
    time_seconds: float
    transform: Transform


class MotionTrack:
    def __init__(self) -> None:
        self.keyframes: list[MotionKeyframe] = []
        self._record_start: float | None = None

    def clear(self) -> None:
        self.keyframes.clear()
        self._record_start = None

    def start(self, transform: Transform) -> None:
        self.clear()
        self._record_start = time.perf_counter()
        self.add(transform)

    def add(self, transform: Transform) -> None:
        if self._record_start is None:
            return
        t = time.perf_counter() - self._record_start
        self.keyframes.append(MotionKeyframe(t, copy_transform(transform)))

    def stop(self, transform: Transform) -> float:
        self.add(transform)
        duration = self.duration
        self._record_start = None
        return duration

    @property
    def duration(self) -> float:
        if not self.keyframes:
            return 0.0
        return max(0.0, self.keyframes[-1].time_seconds)

    def sample(self, time_seconds: float) -> Transform:
        if not self.keyframes:
            return Transform()
        if time_seconds <= self.keyframes[0].time_seconds:
            return copy_transform(self.keyframes[0].transform)
        if time_seconds >= self.keyframes[-1].time_seconds:
            return copy_transform(self.keyframes[-1].transform)

        for left, right in zip(self.keyframes, self.keyframes[1:]):
            if left.time_seconds <= time_seconds <= right.time_seconds:
                span = max(1e-9, right.time_seconds - left.time_seconds)
                amount = (time_seconds - left.time_seconds) / span
                return interpolate_transform(left.transform, right.transform, amount)
        return copy_transform(self.keyframes[-1].transform)


def copy_transform(transform: Transform) -> Transform:
    return Transform(
        rotation_x=transform.rotation_x,
        rotation_y=transform.rotation_y,
        rotation_z=transform.rotation_z,
        offset_x=transform.offset_x,
        offset_y=transform.offset_y,
        zoom=transform.zoom,
    )


def interpolate_transform(a: Transform, b: Transform, amount: float) -> Transform:
    t = min(1.0, max(0.0, float(amount)))

    def lerp(x: float, y: float) -> float:
        return x + (y - x) * t

    return Transform(
        rotation_x=lerp(a.rotation_x, b.rotation_x),
        rotation_y=lerp(a.rotation_y, b.rotation_y),
        rotation_z=lerp(a.rotation_z, b.rotation_z),
        offset_x=lerp(a.offset_x, b.offset_x),
        offset_y=lerp(a.offset_y, b.offset_y),
        zoom=lerp(a.zoom, b.zoom),
    )
