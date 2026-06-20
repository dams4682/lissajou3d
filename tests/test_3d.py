from __future__ import annotations

import struct
import wave

import numpy as np
import pytest

import xy_audio_3d.render as render_module
from xy_audio.engine import export_wav
from xy_audio_3d.geometry import Transform, load_stl_wireframe, make_shape, project_vertices, project_wireframe
from xy_audio_3d.gui import GpuWireframeViewer
from xy_audio_3d.motion import MotionTrack, MotionKeyframe
from xy_audio_3d.render import Render3DConfig, _contours_to_trajectory, build_3d_xy_audio


def test_3d_primitives_have_vertices_and_edges():
    for name in ["cube", "pyramid", "sphere"]:
        shape = make_shape(name)
        assert shape.vertices.shape[1] == 3
        assert len(shape.edges) > 0


def test_ascii_stl_import_builds_normalized_wireframe(tmp_path):
    stl = tmp_path / "triangle.stl"
    stl.write_text(
        """solid triangle
facet normal 0 0 1
  outer loop
    vertex 0 0 0
    vertex 2 0 0
    vertex 0 2 0
  endloop
endfacet
endsolid triangle
""",
        encoding="utf-8",
    )

    wireframe = load_stl_wireframe(stl)

    assert wireframe.vertices.shape == (3, 3)
    assert len(wireframe.edges) == 3
    assert float(np.max(np.abs(wireframe.vertices))) <= 1.0


def test_feature_stl_import_removes_coplanar_mesh_diagonal(tmp_path):
    stl = tmp_path / "square.stl"
    stl.write_text(
        """solid square
facet normal 0 0 1
  outer loop
    vertex 0 0 0
    vertex 1 0 0
    vertex 1 1 0
  endloop
endfacet
facet normal 0 0 1
  outer loop
    vertex 0 0 0
    vertex 1 1 0
    vertex 0 1 0
  endloop
endfacet
endsolid square
""",
        encoding="utf-8",
    )

    feature = load_stl_wireframe(stl, edge_mode="feature_edges", feature_angle_degrees=5, max_edges=None)
    full = load_stl_wireframe(stl, edge_mode="all_edges", max_edges=None)

    assert feature.source_edge_count == 5
    assert len(feature.edges) == 4
    assert len(full.edges) == 5


def test_silhouette_stl_import_uses_view_dependent_outline(tmp_path):
    stl = tmp_path / "square.stl"
    stl.write_text(
        """solid square
facet normal 0 0 1
  outer loop
    vertex 0 0 0
    vertex 1 0 0
    vertex 1 1 0
  endloop
endfacet
facet normal 0 0 1
  outer loop
    vertex 0 0 0
    vertex 1 1 0
    vertex 0 1 0
  endloop
endfacet
endsolid square
""",
        encoding="utf-8",
    )

    wireframe = load_stl_wireframe(stl, edge_mode="silhouette_edges", max_edges=None)
    contours = project_wireframe(wireframe, Transform())

    assert wireframe.source_edge_count == 5
    assert len(contours) == 4


def test_stl_import_can_limit_edges_for_audio_and_preview(tmp_path):
    stl = tmp_path / "tetrahedron.stl"
    stl.write_text(
        """solid tetrahedron
facet normal 0 0 0
  outer loop
    vertex 1 1 1
    vertex -1 -1 1
    vertex -1 1 -1
  endloop
endfacet
facet normal 0 0 0
  outer loop
    vertex 1 1 1
    vertex 1 -1 -1
    vertex -1 -1 1
  endloop
endfacet
facet normal 0 0 0
  outer loop
    vertex 1 1 1
    vertex -1 1 -1
    vertex 1 -1 -1
  endloop
endfacet
facet normal 0 0 0
  outer loop
    vertex -1 -1 1
    vertex 1 -1 -1
    vertex -1 1 -1
  endloop
endfacet
endsolid tetrahedron
""",
        encoding="utf-8",
    )

    wireframe = load_stl_wireframe(stl, edge_mode="all_edges", max_edges=2)

    assert wireframe.source_edge_count == 6
    assert len(wireframe.edges) == 2


def test_binary_stl_import_builds_wireframe_and_audio(tmp_path):
    stl = tmp_path / "triangle_binary.stl"
    header = b"binary test".ljust(80, b"\0")
    triangle = struct.pack(
        "<12fH",
        0.0, 0.0, 1.0,
        0.0, 0.0, 0.0,
        1.0, 0.0, 0.0,
        0.0, 1.0, 0.0,
        0,
    )
    stl.write_bytes(header + struct.pack("<I", 1) + triangle + b"extra")

    wireframe = load_stl_wireframe(stl)
    config = Render3DConfig(duration=0.05, sample_rate=8_000, scan_rate_hz=20, smoothing=1)
    audio = build_3d_xy_audio(config, wireframe=wireframe)

    assert len(wireframe.edges) == 3
    assert audio.shape == (400, 2)
    assert np.isfinite(audio).all()


def test_project_wireframe_returns_finite_xy_edges():
    shape = make_shape("cube")
    contours = project_wireframe(shape, Transform(rotation_x=30, rotation_y=45), projection="perspective")
    assert len(contours) == len(shape.edges)
    all_points = np.vstack(contours)
    assert all_points.shape[1] == 2
    assert np.isfinite(all_points).all()


def test_projection_keeps_stable_camera_scale():
    shape = make_shape("cube")
    face = project_vertices(shape.vertices, Transform(rotation_y=0), projection="orthographic")
    angled = project_vertices(shape.vertices, Transform(rotation_y=45), projection="orthographic")

    face_span = float(np.ptp(face[:, 0]))
    angled_span = float(np.ptp(angled[:, 0]))
    assert face_span == pytest.approx(2.0 / 2.4)
    assert angled_span > face_span


def test_gpu_viewer_has_projection_matrix_method():
    assert hasattr(GpuWireframeViewer, "_projection_matrix")
    assert "_projection_matrix" not in _use_gpu_preview_nested_names()


def _use_gpu_preview_nested_names() -> tuple[str, ...]:
    from xy_audio_3d.gui import _use_gpu_preview

    return _use_gpu_preview.__code__.co_names


def test_motion_track_interpolates_keyframes():
    track = MotionTrack()
    track.keyframes = [
        MotionKeyframe(0.0, Transform(rotation_y=0.0, zoom=1.0)),
        MotionKeyframe(2.0, Transform(rotation_y=100.0, zoom=2.0)),
    ]
    mid = track.sample(1.0)
    assert mid.rotation_y == 50.0
    assert mid.zoom == 1.5


def test_build_3d_xy_audio_is_stereo_normalized(tmp_path):
    config = Render3DConfig(shape="cube", duration=0.25, sample_rate=8_000, scan_rate_hz=20, smoothing=1)
    audio = build_3d_xy_audio(config)
    assert audio.shape == (2_000, 2)
    assert float(np.max(np.abs(audio))) <= 1.0
    assert float(np.std(audio[:, 0])) > 0.01
    assert float(np.std(audio[:, 1])) > 0.01

    out = tmp_path / "cube.wav"
    export_wav(audio, out, config.sample_rate)
    with wave.open(str(out), "rb") as wav:
        assert wav.getnchannels() == 2
        assert wav.getframerate() == 8_000
        assert wav.getnframes() == 2_000


def test_build_3d_xy_audio_accepts_high_scan_rate():
    config = Render3DConfig(shape="cube", duration=0.01, sample_rate=48_000, scan_rate_hz=16_000, smoothing=1)
    audio = build_3d_xy_audio(config)

    assert audio.shape == (480, 2)
    assert np.isfinite(audio).all()
    assert float(np.max(np.abs(audio))) <= 1.0


def test_geometry_rate_limits_projection_rebuilds(monkeypatch):
    calls = 0
    original = render_module.project_wireframe

    def counted_project_wireframe(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(render_module, "project_wireframe", counted_project_wireframe)
    config = Render3DConfig(
        shape="cube",
        duration=1.0,
        sample_rate=8_000,
        scan_rate_hz=40,
        geometry_rate_hz=5,
        smoothing=1,
    )

    audio = build_3d_xy_audio(config)

    assert audio.shape == (8_000, 2)
    assert calls == 5


def test_build_3d_xy_audio_reports_geometry_progress():
    progress: list[tuple[int, int]] = []
    config = Render3DConfig(
        shape="cube",
        duration=1.0,
        sample_rate=8_000,
        scan_rate_hz=40,
        geometry_rate_hz=5,
        smoothing=1,
    )

    audio = build_3d_xy_audio(config, progress_callback=lambda done, total: progress.append((done, total)))

    assert audio.shape == (8_000, 2)
    assert progress
    assert progress[-1] == (5, 5)


def test_wire_walk_avoids_non_edge_jumps_for_cube():
    shape = make_shape("cube")
    contours = project_wireframe(shape, Transform(rotation_x=25, rotation_y=35), projection="orthographic")
    walk = _contours_to_trajectory(contours, mode="wire_walk")

    def key(point: np.ndarray) -> tuple[int, int]:
        return (int(round(float(point[0]) * 1_000_000)), int(round(float(point[1]) * 1_000_000)))

    allowed_edges = {
        tuple(sorted((key(edge[0]), key(edge[1]))))
        for edge in contours
        if float(np.linalg.norm(edge[1] - edge[0])) > 0
    }
    walk_edges = [
        tuple(sorted((key(a), key(b))))
        for a, b in zip(walk, walk[1:])
        if float(np.linalg.norm(b - a)) > 0
    ]

    assert len(walk_edges) >= len(allowed_edges)
    assert walk_edges
    assert set(walk_edges).issubset(allowed_edges)


def test_silhouette_loops_assembles_connected_fragments():
    contours = [
        np.array([[1.0, 1.0], [0.0, 1.0]]),
        np.array([[0.0, 0.0], [1.0, 0.0]]),
        np.array([[0.0, 1.0], [0.0, 0.0]]),
        np.array([[1.0, 0.0], [1.0, 1.0]]),
    ]

    loop = _contours_to_trajectory(contours, mode="silhouette_loops")
    distances = np.linalg.norm(np.diff(loop, axis=0), axis=1)

    assert loop.shape == (5, 2)
    assert np.allclose(distances, 1.0)


def test_nearest_fragments_reorders_disconnected_segments():
    contours = [
        np.array([[0.0, 0.0], [1.0, 0.0]]),
        np.array([[100.0, 0.0], [101.0, 0.0]]),
        np.array([[2.0, 0.0], [3.0, 0.0]]),
    ]

    fast = _contours_to_trajectory(contours, mode="fast_jumps")
    nearest = _contours_to_trajectory(contours, mode="nearest_fragments")

    fast_distance = float(np.sum(np.linalg.norm(np.diff(fast, axis=0), axis=1)))
    nearest_distance = float(np.sum(np.linalg.norm(np.diff(nearest, axis=0), axis=1)))

    assert nearest_distance < fast_distance
    assert nearest_distance == pytest.approx(101.0)
