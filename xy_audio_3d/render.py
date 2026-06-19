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
    trace_mode: str = "wire_walk"
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
        trajectory = _contours_to_trajectory(contours, mode=config.trace_mode)
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


def _contours_to_trajectory(contours: list[np.ndarray], mode: str = "wire_walk") -> np.ndarray:
    if not contours:
        return np.zeros((2, 2), dtype=np.float64)
    if mode == "wire_walk":
        return _wire_walk_trajectory(contours)
    if mode == "nearest_fragments":
        return _nearest_fragment_trajectory(contours)
    pieces: list[np.ndarray] = []
    previous: np.ndarray | None = None
    for contour in contours:
        if previous is not None:
            pieces.append(np.linspace(previous, contour[0], 4, dtype=np.float64)[1:-1])
        pieces.append(contour)
        previous = contour[-1]
    return np.vstack(pieces)


def _nearest_fragment_trajectory(contours: list[np.ndarray]) -> np.ndarray:
    fragments = [np.asarray(contour, dtype=np.float64) for contour in contours if len(contour) >= 2]
    if not fragments:
        return np.vstack(contours)

    remaining = fragments[:]
    current = remaining.pop(0)
    ordered = [current]
    cursor = current[-1]

    while remaining:
        best_index = 0
        best_reverse = False
        best_distance = math.inf
        for index, fragment in enumerate(remaining):
            start_distance = float(np.linalg.norm(fragment[0] - cursor))
            end_distance = float(np.linalg.norm(fragment[-1] - cursor))
            if start_distance < best_distance:
                best_index = index
                best_reverse = False
                best_distance = start_distance
            if end_distance < best_distance:
                best_index = index
                best_reverse = True
                best_distance = end_distance
        next_fragment = remaining.pop(best_index)
        if best_reverse:
            next_fragment = next_fragment[::-1]
        ordered.append(next_fragment)
        cursor = next_fragment[-1]

    pieces: list[np.ndarray] = []
    previous: np.ndarray | None = None
    for fragment in ordered:
        if previous is not None:
            pieces.append(np.linspace(previous, fragment[0], 2, dtype=np.float64)[1:])
        pieces.append(fragment)
        previous = fragment[-1]
    return np.vstack(pieces)


def _wire_walk_trajectory(contours: list[np.ndarray]) -> np.ndarray:
    """Build one continuous walk along existing wire edges.

    This avoids oscilloscope retrace diagonals by traversing between disconnected
    edge segments through already existing wire edges instead of jumping across
    the shape interior.
    """
    vertices, edges = _graph_from_contours(contours)
    if not edges:
        return np.vstack(contours)

    adjacency: dict[int, list[int]] = {i: [] for i in range(len(vertices))}
    unvisited: set[tuple[int, int]] = set()
    for a, b in edges:
        adjacency[a].append(b)
        adjacency[b].append(a)
        unvisited.add(_edge_key(a, b))

    start = edges[0][0]
    walk_indices = _greedy_edge_walk(adjacency, unvisited, start)
    return np.asarray([vertices[i] for i in walk_indices], dtype=np.float64)


def _graph_from_contours(contours: list[np.ndarray]) -> tuple[list[np.ndarray], list[tuple[int, int]]]:
    vertices: list[np.ndarray] = []
    lookup: dict[tuple[int, int], int] = {}
    edges: list[tuple[int, int]] = []
    seen_edges: set[tuple[int, int]] = set()

    def vertex_index(point: np.ndarray) -> int:
        key = (int(round(float(point[0]) * 1_000_000)), int(round(float(point[1]) * 1_000_000)))
        if key not in lookup:
            lookup[key] = len(vertices)
            vertices.append(np.asarray(point, dtype=np.float64))
        return lookup[key]

    for contour in contours:
        if len(contour) < 2:
            continue
        a = vertex_index(contour[0])
        b = vertex_index(contour[-1])
        if a != b:
            key = _edge_key(a, b)
            if key not in seen_edges:
                edges.append((a, b))
                seen_edges.add(key)
    return vertices, edges


def _greedy_edge_walk(adjacency: dict[int, list[int]], unvisited: set[tuple[int, int]], start: int) -> list[int]:
    current = start
    path = [current]

    while unvisited:
        next_vertex = _first_unvisited_neighbor(adjacency, unvisited, current)
        if next_vertex is None:
            target = _nearest_unvisited_endpoint(adjacency, unvisited, current)
            bridge = _shortest_vertex_path(adjacency, current, target)
            path.extend(bridge[1:])
            current = target
            continue
        unvisited.remove(_edge_key(current, next_vertex))
        current = next_vertex
        path.append(current)

    return path


def _first_unvisited_neighbor(adjacency: dict[int, list[int]], unvisited: set[tuple[int, int]], vertex: int) -> int | None:
    for neighbor in adjacency[vertex]:
        if _edge_key(vertex, neighbor) in unvisited:
            return neighbor
    return None


def _nearest_unvisited_endpoint(adjacency: dict[int, list[int]], unvisited: set[tuple[int, int]], start: int) -> int:
    endpoints = {vertex for edge in unvisited for vertex in edge}
    queue = [start]
    previous: dict[int, int | None] = {start: None}
    for vertex in queue:
        if vertex in endpoints:
            return vertex
        for neighbor in adjacency[vertex]:
            if neighbor not in previous:
                previous[neighbor] = vertex
                queue.append(neighbor)
    return next(iter(endpoints))


def _shortest_vertex_path(adjacency: dict[int, list[int]], start: int, target: int) -> list[int]:
    if start == target:
        return [start]
    queue = [start]
    previous: dict[int, int | None] = {start: None}
    for vertex in queue:
        if vertex == target:
            break
        for neighbor in adjacency[vertex]:
            if neighbor not in previous:
                previous[neighbor] = vertex
                queue.append(neighbor)

    if target not in previous:
        return [start, target]

    path = [target]
    cursor = target
    while previous[cursor] is not None:
        cursor = previous[cursor]
        path.append(cursor)
    return path[::-1]


def _edge_key(a: int, b: int) -> tuple[int, int]:
    return (a, b) if a <= b else (b, a)


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
