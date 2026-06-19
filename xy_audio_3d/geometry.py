from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
import struct

import numpy as np


@dataclass(slots=True)
class Transform:
    rotation_x: float = 0.0
    rotation_y: float = 0.0
    rotation_z: float = 0.0
    offset_x: float = 0.0
    offset_y: float = 0.0
    zoom: float = 1.0


@dataclass(slots=True)
class Wireframe:
    vertices: np.ndarray
    edges: list[tuple[int, int]]
    source_edge_count: int | None = None
    source_vertex_count: int | None = None


def make_shape(name: str, detail: int = 16) -> Wireframe:
    shape = name.strip().lower()
    if shape == "cube":
        return cube()
    if shape == "pyramid":
        return pyramid()
    if shape in {"sphere", "sphere wire", "wire sphere"}:
        return sphere_wire(detail=detail)
    raise ValueError(f"Unknown 3D shape: {name}")


def load_stl_wireframe(
    path: str | Path,
    edge_mode: str = "feature_edges",
    feature_angle_degrees: float = 25.0,
    max_edges: int | None = 8_000,
) -> Wireframe:
    data = Path(path).read_bytes()
    triangles = _read_binary_stl(data) if _looks_like_binary_stl(data) else _read_ascii_stl(data)
    if not triangles:
        raise ValueError("STL file does not contain any triangle.")
    return _wireframe_from_triangles(
        triangles,
        edge_mode=edge_mode,
        feature_angle_degrees=feature_angle_degrees,
        max_edges=max_edges,
    )


def cube() -> Wireframe:
    vertices = np.array(
        [
            [-1, -1, -1],
            [1, -1, -1],
            [1, 1, -1],
            [-1, 1, -1],
            [-1, -1, 1],
            [1, -1, 1],
            [1, 1, 1],
            [-1, 1, 1],
        ],
        dtype=np.float64,
    )
    edges = [
        (0, 1),
        (1, 2),
        (2, 3),
        (3, 0),
        (4, 5),
        (5, 6),
        (6, 7),
        (7, 4),
        (0, 4),
        (1, 5),
        (2, 6),
        (3, 7),
    ]
    return Wireframe(vertices, edges)


def pyramid() -> Wireframe:
    vertices = np.array(
        [
            [-1, -1, -1],
            [1, -1, -1],
            [1, -1, 1],
            [-1, -1, 1],
            [0, 1, 0],
        ],
        dtype=np.float64,
    )
    edges = [(0, 1), (1, 2), (2, 3), (3, 0), (0, 4), (1, 4), (2, 4), (3, 4)]
    return Wireframe(vertices, edges)


def sphere_wire(detail: int = 16) -> Wireframe:
    detail = max(8, int(detail))
    vertices: list[list[float]] = []
    edges: list[tuple[int, int]] = []

    def add_ring(axis: str, radius: float = 1.0) -> None:
        start = len(vertices)
        for i in range(detail):
            theta = 2.0 * math.pi * i / detail
            c = math.cos(theta) * radius
            s = math.sin(theta) * radius
            if axis == "xy":
                vertices.append([c, s, 0.0])
            elif axis == "xz":
                vertices.append([c, 0.0, s])
            else:
                vertices.append([0.0, c, s])
        for i in range(detail):
            edges.append((start + i, start + ((i + 1) % detail)))

    add_ring("xy")
    add_ring("xz")
    add_ring("yz")
    return Wireframe(np.asarray(vertices, dtype=np.float64), edges)


def _looks_like_binary_stl(data: bytes) -> bool:
    if len(data) < 84:
        return False
    triangle_count = struct.unpack_from("<I", data, 80)[0]
    return len(data) >= 84 + triangle_count * 50


def _read_binary_stl(data: bytes) -> list[np.ndarray]:
    triangle_count = struct.unpack_from("<I", data, 80)[0]
    triangles: list[np.ndarray] = []
    offset = 84
    for _ in range(triangle_count):
        values = struct.unpack_from("<9f", data, offset + 12)
        triangle = np.asarray(values, dtype=np.float64).reshape(3, 3)
        if np.isfinite(triangle).all():
            triangles.append(triangle)
        offset += 50
    return triangles


def _read_ascii_stl(data: bytes) -> list[np.ndarray]:
    text = data.decode("utf-8", errors="ignore")
    vertices: list[list[float]] = []
    triangles: list[np.ndarray] = []
    for line in text.splitlines():
        parts = line.strip().split()
        if len(parts) == 4 and parts[0].lower() == "vertex":
            try:
                vertices.append([float(parts[1]), float(parts[2]), float(parts[3])])
            except ValueError:
                continue
            if len(vertices) == 3:
                triangle = np.asarray(vertices, dtype=np.float64)
                if np.isfinite(triangle).all():
                    triangles.append(triangle)
                vertices = []
    return triangles


def _wireframe_from_triangles(
    triangles: list[np.ndarray],
    edge_mode: str = "feature_edges",
    feature_angle_degrees: float = 25.0,
    max_edges: int | None = 8_000,
) -> Wireframe:
    vertices: list[np.ndarray] = []
    vertex_lookup: dict[tuple[int, int, int], int] = {}
    edge_faces: dict[tuple[int, int], list[int]] = {}
    normals: list[np.ndarray] = []

    def vertex_index(point: np.ndarray) -> int:
        key = (
            int(round(float(point[0]) * 1_000_000)),
            int(round(float(point[1]) * 1_000_000)),
            int(round(float(point[2]) * 1_000_000)),
        )
        if key not in vertex_lookup:
            vertex_lookup[key] = len(vertices)
            vertices.append(np.asarray(point, dtype=np.float64))
        return vertex_lookup[key]

    for triangle in triangles:
        indexes = [vertex_index(point) for point in triangle]
        normals.append(_triangle_normal(triangle))
        for a, b in ((indexes[0], indexes[1]), (indexes[1], indexes[2]), (indexes[2], indexes[0])):
            if a == b:
                continue
            key = (a, b) if a <= b else (b, a)
            edge_faces.setdefault(key, []).append(len(normals) - 1)

    source_edge_count = len(edge_faces)
    source_vertex_count = len(vertices)
    edges = _select_stl_edges(edge_faces, normals, edge_mode, feature_angle_degrees)
    edges = _limit_edges_by_length(edges, vertices, max_edges)
    if not vertices or not edges:
        raise ValueError("STL file does not contain a usable wireframe.")
    return Wireframe(
        _normalize_vertices(np.asarray(vertices, dtype=np.float64)),
        edges,
        source_edge_count=source_edge_count,
        source_vertex_count=source_vertex_count,
    )


def _triangle_normal(triangle: np.ndarray) -> np.ndarray:
    a, b, c = triangle
    normal = np.cross(b - a, c - a)
    length = float(np.linalg.norm(normal))
    if length <= 1e-12:
        return np.zeros(3, dtype=np.float64)
    return normal / length


def _select_stl_edges(
    edge_faces: dict[tuple[int, int], list[int]],
    normals: list[np.ndarray],
    edge_mode: str,
    feature_angle_degrees: float,
) -> list[tuple[int, int]]:
    if edge_mode == "all_edges":
        return list(edge_faces)

    threshold = max(0.0, min(180.0, float(feature_angle_degrees)))
    selected: list[tuple[int, int]] = []
    for edge, faces in edge_faces.items():
        if len(faces) != 2:
            selected.append(edge)
            continue
        left = normals[faces[0]]
        right = normals[faces[1]]
        if float(np.linalg.norm(left)) <= 0 or float(np.linalg.norm(right)) <= 0:
            selected.append(edge)
            continue
        dot = max(-1.0, min(1.0, float(np.dot(left, right))))
        angle = math.degrees(math.acos(dot))
        if angle >= threshold:
            selected.append(edge)

    return selected or list(edge_faces)


def _limit_edges_by_length(
    edges: list[tuple[int, int]],
    vertices: list[np.ndarray],
    max_edges: int | None,
) -> list[tuple[int, int]]:
    if max_edges is None or max_edges <= 0 or len(edges) <= max_edges:
        return edges
    ranked = sorted(
        edges,
        key=lambda edge: float(np.linalg.norm(vertices[edge[1]] - vertices[edge[0]])),
        reverse=True,
    )
    return ranked[:max_edges]


def _normalize_vertices(vertices: np.ndarray) -> np.ndarray:
    normalized = np.asarray(vertices, dtype=np.float64).copy()
    mins = np.min(normalized, axis=0)
    maxs = np.max(normalized, axis=0)
    normalized -= (mins + maxs) / 2.0
    span = float(np.max(maxs - mins))
    if span > 0:
        normalized /= span / 2.0
    return normalized


def apply_transform(vertices: np.ndarray, transform: Transform) -> np.ndarray:
    rotated = vertices @ rotation_matrix(transform).T
    rotated[:, 0] += transform.offset_x
    rotated[:, 1] += transform.offset_y
    return rotated * max(0.001, float(transform.zoom))


def rotation_matrix(transform: Transform) -> np.ndarray:
    rx = math.radians(transform.rotation_x)
    ry = math.radians(transform.rotation_y)
    rz = math.radians(transform.rotation_z)
    cx, sx = math.cos(rx), math.sin(rx)
    cy, sy = math.cos(ry), math.sin(ry)
    cz, sz = math.cos(rz), math.sin(rz)
    mx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]], dtype=np.float64)
    my = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]], dtype=np.float64)
    mz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]], dtype=np.float64)
    return mz @ my @ mx


def project_vertices(
    vertices: np.ndarray,
    transform: Transform,
    projection: str = "orthographic",
    perspective: float = 2.8,
    view_scale: float = 2.4,
) -> np.ndarray:
    transformed = apply_transform(vertices.copy(), transform)
    if projection == "perspective":
        distance = max(1.1, float(perspective))
        z = transformed[:, 2]
        factor = distance / np.maximum(0.15, distance - z)
        xy = transformed[:, :2] * factor[:, None]
    else:
        xy = transformed[:, :2]
    return xy / max(0.001, float(view_scale))


def project_wireframe(
    wireframe: Wireframe,
    transform: Transform,
    projection: str = "orthographic",
    perspective: float = 2.8,
    view_scale: float = 2.4,
) -> list[np.ndarray]:
    xy = project_vertices(
        wireframe.vertices,
        transform,
        projection=projection,
        perspective=perspective,
        view_scale=view_scale,
    )
    return [xy[[a, b]] for a, b in wireframe.edges]
