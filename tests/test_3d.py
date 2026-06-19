from __future__ import annotations

import struct
import wave

import numpy as np
import pytest

from xy_audio.engine import export_wav
from xy_audio_3d.geometry import Transform, load_stl_wireframe, make_shape, project_vertices, project_wireframe
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
