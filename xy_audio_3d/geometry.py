from __future__ import annotations

from dataclasses import dataclass
import math

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


def make_shape(name: str, detail: int = 16) -> Wireframe:
    shape = name.strip().lower()
    if shape == "cube":
        return cube()
    if shape == "pyramid":
        return pyramid()
    if shape in {"sphere", "sphere wire", "wire sphere"}:
        return sphere_wire(detail=detail)
    raise ValueError(f"Unknown 3D shape: {name}")


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
