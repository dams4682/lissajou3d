from __future__ import annotations

import os
from pathlib import Path
import sys
import winsound

import numpy as np
from PyQt6.QtCore import QObject, QPoint, Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QMatrix4x4, QPainter, QPalette, QPen
from PyQt6.QtOpenGL import QOpenGLBuffer, QOpenGLFunctions_2_0, QOpenGLShader, QOpenGLShaderProgram
from PyQt6.QtOpenGLWidgets import QOpenGLWidget
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from xy_audio.audition import write_temp_wav
from xy_audio.engine import export_wav
from .geometry import Transform, Wireframe, load_stl_wireframe, make_shape, project_wireframe, wireframe_edges_for_transform
from .motion import MotionTrack, copy_transform
from .render import Render3DConfig, build_3d_xy_audio


class RenderWorker(QObject):
    finished = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, config: Render3DConfig, motion: MotionTrack | None, wireframe: Wireframe | None) -> None:
        super().__init__()
        self.config = config
        self.motion = motion
        self.wireframe = wireframe

    def run(self) -> None:
        try:
            audio = build_3d_xy_audio(self.config, motion=self.motion, wireframe=self.wireframe)
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.finished.emit((audio, self.config.sample_rate))


class GpuWireframeViewer(QOpenGLWidget):
    transform_changed = pyqtSignal(object)
    GL_COLOR_BUFFER_BIT = 0x00004000
    GL_DEPTH_BUFFER_BIT = 0x00000100
    GL_DEPTH_TEST = 0x0B71
    GL_LINES = 0x0001
    GL_UNSIGNED_INT = 0x1405

    def __init__(self) -> None:
        super().__init__()
        self.shape_name = "cube"
        self.object_label = "cube"
        self.custom_wireframe: Wireframe | None = None
        self.projection = "orthographic"
        self.perspective = 2.8
        self.view_scale = 2.4
        self.transform = Transform(rotation_x=25.0, rotation_y=-30.0, rotation_z=0.0, zoom=1.0)
        self._last_pos: QPoint | None = None
        self.functions: QOpenGLFunctions_2_0 | None = None
        self.program: QOpenGLShaderProgram | None = None
        self.vertex_buffer: QOpenGLBuffer | None = None
        self.index_buffer: QOpenGLBuffer | None = None
        self.grid_vertex_buffer: QOpenGLBuffer | None = None
        self.grid_index_buffer: QOpenGLBuffer | None = None
        self.index_count = 0
        self.grid_index_count = 0
        self.pending_wireframe: Wireframe | None = None
        self.current_wireframe: Wireframe = make_shape("cube")
        self.setMinimumSize(520, 420)
        self.setMouseTracking(True)

    def set_shape(self, name: str) -> None:
        self.shape_name = name
        self.object_label = name
        self.custom_wireframe = None
        self.current_wireframe = make_shape(name)
        self._upload_wireframe_later(self.current_wireframe)
        self.update()

    def set_wireframe(self, wireframe: Wireframe, label: str) -> None:
        self.custom_wireframe = wireframe
        self.object_label = label
        self.current_wireframe = wireframe
        self._upload_wireframe_later(wireframe)
        self.update()

    def set_projection(self, projection: str, perspective: float, view_scale: float = 2.4) -> None:
        self.projection = projection
        self.perspective = perspective
        self.view_scale = view_scale
        self.update()

    def reset_view(self) -> None:
        self.transform = Transform(rotation_x=25.0, rotation_y=-30.0, rotation_z=0.0, zoom=1.0)
        self.transform_changed.emit(copy_transform(self.transform))
        self.update()

    def initializeGL(self) -> None:  # noqa: N802 - Qt naming
        self.functions = QOpenGLFunctions_2_0()
        self.functions.initializeOpenGLFunctions()
        self.functions.glClearColor(0.063, 0.078, 0.094, 1.0)
        self.functions.glEnable(self.GL_DEPTH_TEST)
        self.program = QOpenGLShaderProgram(self)
        self.program.addShaderFromSourceCode(
            QOpenGLShader.ShaderTypeBit.Vertex,
            """
            attribute vec3 position;
            uniform mat4 mvp;
            void main() {
                gl_Position = mvp * vec4(position, 1.0);
            }
            """,
        )
        self.program.addShaderFromSourceCode(
            QOpenGLShader.ShaderTypeBit.Fragment,
            """
            uniform vec4 color;
            void main() {
                gl_FragColor = color;
            }
            """,
        )
        self.program.bindAttributeLocation("position", 0)
        self.program.link()

        self.vertex_buffer = QOpenGLBuffer(QOpenGLBuffer.Type.VertexBuffer)
        self.vertex_buffer.create()
        self.vertex_buffer.setUsagePattern(QOpenGLBuffer.UsagePattern.StaticDraw)
        self.index_buffer = QOpenGLBuffer(QOpenGLBuffer.Type.IndexBuffer)
        self.index_buffer.create()
        self.index_buffer.setUsagePattern(QOpenGLBuffer.UsagePattern.StaticDraw)
        self.grid_vertex_buffer = QOpenGLBuffer(QOpenGLBuffer.Type.VertexBuffer)
        self.grid_vertex_buffer.create()
        self.grid_vertex_buffer.setUsagePattern(QOpenGLBuffer.UsagePattern.StaticDraw)
        self.grid_index_buffer = QOpenGLBuffer(QOpenGLBuffer.Type.IndexBuffer)
        self.grid_index_buffer.create()
        self.grid_index_buffer.setUsagePattern(QOpenGLBuffer.UsagePattern.StaticDraw)

        self._upload_grid()
        self._upload_wireframe(self.current_wireframe)

    def resizeGL(self, width: int, height: int) -> None:  # noqa: N802 - Qt naming
        if self.functions:
            self.functions.glViewport(0, 0, max(1, width), max(1, height))

    def paintGL(self) -> None:  # noqa: N802 - Qt naming
        if not self.functions or not self.program:
            return
        if self.pending_wireframe is not None:
            self._upload_wireframe(self.pending_wireframe)
            self.pending_wireframe = None

        self.functions.glClear(self.GL_COLOR_BUFFER_BIT | self.GL_DEPTH_BUFFER_BIT)
        self.program.bind()
        self.functions.glLineWidth(1.0)
        self._draw_lines(self.grid_vertex_buffer, self.grid_index_buffer, self.grid_index_count, self._grid_matrix(), QColor("#26313a"))
        self.functions.glLineWidth(1.6)
        if self.current_wireframe.line_mode in {"silhouette_edges", "silhouette_feature"}:
            self._upload_indices(wireframe_edges_for_transform(self.current_wireframe, self.transform))
        self._draw_lines(self.vertex_buffer, self.index_buffer, self.index_count, self._object_matrix(), QColor("#00d1b2"))
        self.program.release()

        painter = QPainter(self)
        painter.setPen(QColor("#aab4bf"))
        painter.drawText(16, 24, f"{self.object_label} - drag to rotate, wheel to zoom, right-drag to move")
        painter.end()

    def mousePressEvent(self, event) -> None:  # noqa: N802 - Qt naming
        self._last_pos = event.position().toPoint()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802 - Qt naming
        if self._last_pos is None:
            return
        pos = event.position().toPoint()
        dx = pos.x() - self._last_pos.x()
        dy = pos.y() - self._last_pos.y()
        buttons = event.buttons()
        if buttons & Qt.MouseButton.LeftButton:
            self.transform.rotation_y += dx * 0.5
            self.transform.rotation_x += dy * 0.5
        elif buttons & Qt.MouseButton.RightButton:
            self.transform.offset_x += dx / max(1, self.width()) * 2.0
            self.transform.offset_y -= dy / max(1, self.height()) * 2.0
        self._last_pos = pos
        self.transform_changed.emit(copy_transform(self.transform))
        self.update()

    def mouseReleaseEvent(self, _event) -> None:  # noqa: N802 - Qt naming
        self._last_pos = None

    def wheelEvent(self, event) -> None:  # noqa: N802 - Qt naming
        delta = event.angleDelta().y()
        factor = 1.1 if delta > 0 else 1.0 / 1.1
        self.transform.zoom = min(4.0, max(0.2, self.transform.zoom * factor))
        self.transform_changed.emit(copy_transform(self.transform))
        self.update()

    def _upload_wireframe_later(self, wireframe: Wireframe) -> None:
        if self.context() is None or not self.isValid():
            self.pending_wireframe = wireframe
            return
        self.makeCurrent()
        self._upload_wireframe(wireframe)
        self.doneCurrent()

    def _upload_wireframe(self, wireframe: Wireframe) -> None:
        if not self.vertex_buffer or not self.index_buffer:
            return
        vertices = np.asarray(wireframe.vertices, dtype=np.float32)
        self.vertex_buffer.bind()
        self.vertex_buffer.allocate(vertices.tobytes(), vertices.nbytes)
        self.vertex_buffer.release()
        self._upload_indices(wireframe.edges)

    def _upload_indices(self, edges: list[tuple[int, int]]) -> None:
        if not self.index_buffer:
            return
        indices = np.asarray([index for edge in edges for index in edge], dtype=np.uint32)
        self.index_buffer.bind()
        self.index_buffer.allocate(indices.tobytes(), indices.nbytes)
        self.index_buffer.release()
        self.index_count = int(len(indices))

    def _upload_grid(self) -> None:
        if not self.grid_vertex_buffer or not self.grid_index_buffer:
            return
        vertices: list[tuple[float, float, float]] = []
        indices: list[int] = []

        def add_line(a: tuple[float, float, float], b: tuple[float, float, float]) -> None:
            start = len(vertices)
            vertices.extend((a, b))
            indices.extend((start, start + 1))

        for i in range(5):
            value = -1.0 + i * 0.5
            add_line((value, -1.0, 0.0), (value, 1.0, 0.0))
            add_line((-1.0, value, 0.0), (1.0, value, 0.0))
        add_line((-1.0, -1.0, 0.0), (1.0, -1.0, 0.0))
        add_line((1.0, -1.0, 0.0), (1.0, 1.0, 0.0))
        add_line((1.0, 1.0, 0.0), (-1.0, 1.0, 0.0))
        add_line((-1.0, 1.0, 0.0), (-1.0, -1.0, 0.0))

        vertex_array = np.asarray(vertices, dtype=np.float32)
        index_array = np.asarray(indices, dtype=np.uint32)
        self.grid_vertex_buffer.bind()
        self.grid_vertex_buffer.allocate(vertex_array.tobytes(), vertex_array.nbytes)
        self.grid_vertex_buffer.release()
        self.grid_index_buffer.bind()
        self.grid_index_buffer.allocate(index_array.tobytes(), index_array.nbytes)
        self.grid_index_buffer.release()
        self.grid_index_count = int(len(index_array))

    def _draw_lines(
        self,
        vertex_buffer: QOpenGLBuffer | None,
        index_buffer: QOpenGLBuffer | None,
        index_count: int,
        matrix: QMatrix4x4,
        color: QColor,
    ) -> None:
        if not self.functions or not self.program or not vertex_buffer or not index_buffer or index_count <= 0:
            return
        self.program.setUniformValue("mvp", matrix)
        self.program.setUniformValue("color", color)
        vertex_buffer.bind()
        index_buffer.bind()
        self.program.enableAttributeArray(0)
        self.program.setAttributeBuffer(0, 0x1406, 0, 3, 0)
        self.functions.glDrawElements(self.GL_LINES, index_count, self.GL_UNSIGNED_INT, None)
        self.program.disableAttributeArray(0)
        index_buffer.release()
        vertex_buffer.release()

    def _object_matrix(self) -> QMatrix4x4:
        matrix = self._projection_matrix()
        model = QMatrix4x4()
        model.translate(float(self.transform.offset_x), float(self.transform.offset_y), 0.0)
        model.scale(max(0.001, float(self.transform.zoom)))
        model.rotate(float(self.transform.rotation_z), 0.0, 0.0, 1.0)
        model.rotate(float(self.transform.rotation_y), 0.0, 1.0, 0.0)
        model.rotate(float(self.transform.rotation_x), 1.0, 0.0, 0.0)
        return matrix * model

    def _grid_matrix(self) -> QMatrix4x4:
        matrix = QMatrix4x4()
        matrix.ortho(-1.0, 1.0, -1.0, 1.0, -1.0, 1.0)
        return matrix


class CpuWireframeViewer(QWidget):
    transform_changed = pyqtSignal(object)

    def __init__(self) -> None:
        super().__init__()
        self.shape_name = "cube"
        self.object_label = "cube"
        self.custom_wireframe: Wireframe | None = None
        self.projection = "orthographic"
        self.perspective = 2.8
        self.view_scale = 2.4
        self.transform = Transform(rotation_x=25.0, rotation_y=-30.0, rotation_z=0.0, zoom=1.0)
        self._last_pos: QPoint | None = None
        self.setMinimumSize(520, 420)
        self.setMouseTracking(True)

    def set_shape(self, name: str) -> None:
        self.shape_name = name
        self.object_label = name
        self.custom_wireframe = None
        self.update()

    def set_wireframe(self, wireframe: Wireframe, label: str) -> None:
        self.custom_wireframe = wireframe
        self.object_label = label
        self.update()

    def set_projection(self, projection: str, perspective: float, view_scale: float = 2.4) -> None:
        self.projection = projection
        self.perspective = perspective
        self.view_scale = view_scale
        self.update()

    def reset_view(self) -> None:
        self.transform = Transform(rotation_x=25.0, rotation_y=-30.0, rotation_z=0.0, zoom=1.0)
        self.transform_changed.emit(copy_transform(self.transform))
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802 - Qt naming
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#101418"))

        side = max(16, min(self.width(), self.height()) - 48)
        left = (self.width() - side) / 2
        top = (self.height() - side) / 2

        painter.setPen(QPen(QColor("#26313a"), 1))
        for i in range(5):
            x = left + side * i / 4
            y = top + side * i / 4
            painter.drawLine(int(x), int(top), int(x), int(top + side))
            painter.drawLine(int(left), int(y), int(left + side), int(y))
        painter.setPen(QPen(QColor("#3a4652"), 1))
        painter.drawRect(int(left), int(top), int(side), int(side))

        try:
            wireframe = self.custom_wireframe or make_shape(self.shape_name)
            contours = project_wireframe(
                wireframe,
                self.transform,
                projection=self.projection,
                perspective=self.perspective,
                view_scale=self.view_scale,
            )
        except Exception:
            contours = []

        painter.setPen(QPen(QColor("#00d1b2"), 2.0))
        for contour in contours:
            a, b = contour
            x1, y1 = self._map_point(a, left, top, side)
            x2, y2 = self._map_point(b, left, top, side)
            painter.drawLine(x1, y1, x2, y2)

        painter.setPen(QColor("#aab4bf"))
        painter.drawText(16, 24, f"{self.object_label} - drag to rotate, wheel to zoom, right-drag to move")
        painter.end()

    def mousePressEvent(self, event) -> None:  # noqa: N802 - Qt naming
        self._last_pos = event.position().toPoint()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802 - Qt naming
        if self._last_pos is None:
            return
        pos = event.position().toPoint()
        dx = pos.x() - self._last_pos.x()
        dy = pos.y() - self._last_pos.y()
        buttons = event.buttons()
        if buttons & Qt.MouseButton.LeftButton:
            self.transform.rotation_y += dx * 0.5
            self.transform.rotation_x += dy * 0.5
        elif buttons & Qt.MouseButton.RightButton:
            self.transform.offset_x += dx / max(1, self.width()) * 2.0
            self.transform.offset_y -= dy / max(1, self.height()) * 2.0
        self._last_pos = pos
        self.transform_changed.emit(copy_transform(self.transform))
        self.update()

    def mouseReleaseEvent(self, _event) -> None:  # noqa: N802 - Qt naming
        self._last_pos = None

    def wheelEvent(self, event) -> None:  # noqa: N802 - Qt naming
        delta = event.angleDelta().y()
        factor = 1.1 if delta > 0 else 1.0 / 1.1
        self.transform.zoom = min(4.0, max(0.2, self.transform.zoom * factor))
        self.transform_changed.emit(copy_transform(self.transform))
        self.update()

    @staticmethod
    def _map_point(point: np.ndarray, left: float, top: float, side: float) -> tuple[int, int]:
        x = left + (float(point[0]) + 1.0) * 0.5 * side
        y = top + (1.0 - (float(point[1]) + 1.0) * 0.5) * side
        return int(x), int(y)


def _use_gpu_preview() -> bool:
    value = os.environ.get("LISS3D_GPU_PREVIEW", "").strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    return not getattr(sys, "frozen", False)

    def _projection_matrix(self) -> QMatrix4x4:
        aspect = max(0.001, self.width() / max(1, self.height()))
        scale = max(0.001, float(self.view_scale))
        matrix = QMatrix4x4()
        if self.projection == "perspective":
            matrix.perspective(45.0, aspect, 0.1, 100.0)
            view = QMatrix4x4()
            view.translate(0.0, 0.0, -max(1.2, float(self.perspective)))
            return matrix * view
        if aspect >= 1.0:
            matrix.ortho(-scale * aspect, scale * aspect, -scale, scale, -100.0, 100.0)
        else:
            matrix.ortho(-scale, scale, -scale / aspect, scale / aspect, -100.0, 100.0)
        return matrix


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Lissajou3D")
        self.resize(1180, 760)
        self.motion = MotionTrack()
        self.recording = False
        self.current_audio: np.ndarray | None = None
        self.current_audio_sample_rate = 48_000
        self.custom_wireframe: Wireframe | None = None
        self.stl_path: Path | None = None
        self.stl_settings_signature: tuple[str, float, int | None] | None = None
        self.render_thread: QThread | None = None
        self.render_worker: RenderWorker | None = None
        self.render_export_path: str | None = None
        self.render_play_after = False
        self.temp_playback_files: list[Path] = []
        self._build_ui()
        self._apply_theme()

    def _build_ui(self) -> None:
        root = QWidget()
        layout = QHBoxLayout(root)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(18)

        controls = QFrame()
        controls.setMinimumWidth(430)
        controls.setMaximumWidth(560)
        controls_layout = QVBoxLayout(controls)
        controls_layout.setSpacing(14)

        shape_box = QGroupBox("3D Object")
        shape_form = QFormLayout(shape_box)
        shape_form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        self.shape = QComboBox()
        self.shape.addItems(["cube", "pyramid", "sphere"])
        self.use_shape_btn = QPushButton("Use Shape")
        self.use_shape_btn.clicked.connect(lambda: self.select_primitive(self.shape.currentText()))
        self.import_stl_btn = QPushButton("Import STL")
        self.import_stl_btn.clicked.connect(self.import_stl_dialog)
        self.apply_stl_btn = QPushButton("Apply STL Settings")
        self.apply_stl_btn.clicked.connect(self.reload_stl)
        self.stl_edge_mode = QComboBox()
        self.stl_edge_mode.addItems(["silhouette_feature", "silhouette_edges", "feature_edges", "all_edges"])
        self.stl_feature_angle = _double_spin(0.0, 180.0, 25.0, 1.0)
        self.stl_max_edges = _spin(0, 1_000_000, 8_000, 500)
        self.stl_status = QLabel("Primitive shape")
        self.stl_status.setWordWrap(True)
        self.projection = QComboBox()
        self.projection.addItems(["orthographic", "perspective"])
        self.perspective = _double_spin(0.001, 1_000_000.0, 2.8, 0.1)
        self.view_scale = _double_spin(0.001, 1_000_000.0, 2.4, 0.1)
        self.trace_mode = QComboBox()
        self.trace_mode.addItems(["wire_walk", "nearest_fragments", "fast_jumps"])
        shape_form.addRow("Shape", self.shape)
        shape_form.addRow("Primitive", self.use_shape_btn)
        shape_form.addRow("STL", self.import_stl_btn)
        shape_form.addRow("STL edge mode", self.stl_edge_mode)
        shape_form.addRow("Feature angle", self.stl_feature_angle)
        shape_form.addRow("Max STL edges", self.stl_max_edges)
        shape_form.addRow("Apply", self.apply_stl_btn)
        shape_form.addRow("Source", self.stl_status)
        shape_form.addRow("Projection", self.projection)
        shape_form.addRow("Perspective", self.perspective)
        shape_form.addRow("Camera scale", self.view_scale)
        shape_form.addRow("Trace mode", self.trace_mode)
        controls_layout.addWidget(shape_box)

        render_box = QGroupBox("Audio Render")
        form = QFormLayout(render_box)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        self.duration = _double_spin(0.001, 86_400.0, 5.0, 0.1)
        self.sample_rate = _spin(1, 2_147_483_647, 48_000, 1_000)
        self.scan_rate_hz = _double_spin(0.0, 1_000_000.0, 40.0, 1.0)
        self.geometry_rate_hz = _double_spin(0.1, 1_000_000.0, 8.0, 1.0)
        self.scan_note = QComboBox()
        self.scan_note.addItems([
            "",
            "C1", "D1", "E1", "F1", "G1", "A1", "B1",
            "C2", "D2", "E2", "F2", "G2", "A2", "B2",
            "C3", "F3", "C4", "C5", "C6", "C7", "C8", "C9", "C10",
        ])
        self.scan_note.setEditable(True)
        self.scale = _double_spin(0.001, 1_000_000.0, 0.9, 0.05)
        self.smoothing = _spin(1, 100_001, 1, 2)
        self.normalize = QCheckBox()
        self.normalize.setChecked(True)
        self.invert_x = QCheckBox()
        self.invert_y = QCheckBox()
        self.invert_y.setChecked(True)
        form.addRow("Duration", self.duration)
        form.addRow("Sample rate", self.sample_rate)
        form.addRow("Scan rate Hz", self.scan_rate_hz)
        form.addRow("Geometry FPS", self.geometry_rate_hz)
        form.addRow("Scan note", self.scan_note)
        form.addRow("Scale", self.scale)
        form.addRow("Smoothing", self.smoothing)
        form.addRow("Normalize", self.normalize)
        form.addRow("Invert X", self.invert_x)
        form.addRow("Invert Y", self.invert_y)
        controls_layout.addWidget(render_box)

        record_row = QHBoxLayout()
        self.record_btn = QPushButton("Record Movement")
        self.record_btn.clicked.connect(self.toggle_recording)
        stop_btn = QPushButton("Stop")
        stop_btn.clicked.connect(self.stop_all)
        reset_btn = QPushButton("Reset")
        reset_btn.clicked.connect(self.reset)
        record_row.addWidget(self.record_btn)
        record_row.addWidget(stop_btn)
        record_row.addWidget(reset_btn)
        controls_layout.addLayout(record_row)

        action_row = QHBoxLayout()
        self.preview_btn = QPushButton("Render Preview")
        self.preview_btn.clicked.connect(self.render_audio)
        self.play_btn = QPushButton("Play XY")
        self.play_btn.clicked.connect(self.play_xy)
        self.export_btn = QPushButton("Export WAV")
        self.export_btn.clicked.connect(self.export_wav_dialog)
        action_row.addWidget(self.preview_btn)
        action_row.addWidget(self.play_btn)
        action_row.addWidget(self.export_btn)
        controls_layout.addLayout(action_row)
        controls_layout.addStretch(1)

        self.viewer = GpuWireframeViewer() if _use_gpu_preview() else CpuWireframeViewer()
        self.viewer.transform_changed.connect(self.on_transform_changed)
        self.shape.currentTextChanged.connect(self.select_primitive)
        self.projection.currentTextChanged.connect(self._update_viewer_projection)
        self.perspective.valueChanged.connect(self._update_viewer_projection)
        self.view_scale.valueChanged.connect(self._update_viewer_projection)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(controls)
        scroll.setMinimumWidth(460)
        scroll.setMaximumWidth(590)
        layout.addWidget(scroll)
        layout.addWidget(self.viewer, 1)
        self.setCentralWidget(root)
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Ready")
        self._connect_render_dirty_signals()

    def _apply_theme(self) -> None:
        app = QApplication.instance()
        if app:
            app.setStyle("Fusion")
            palette = QPalette()
            palette.setColor(QPalette.ColorRole.Window, QColor("#151a1f"))
            palette.setColor(QPalette.ColorRole.WindowText, QColor("#e8eef4"))
            palette.setColor(QPalette.ColorRole.Base, QColor("#101418"))
            palette.setColor(QPalette.ColorRole.Text, QColor("#e8eef4"))
            palette.setColor(QPalette.ColorRole.Button, QColor("#26313a"))
            palette.setColor(QPalette.ColorRole.ButtonText, QColor("#e8eef4"))
            palette.setColor(QPalette.ColorRole.Highlight, QColor("#00a98f"))
            app.setPalette(palette)
        self.setStyleSheet(
            """
            QGroupBox { border: 1px solid #33404a; border-radius: 6px; margin-top: 10px; padding: 10px; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
            QPushButton { border: 1px solid #40505d; border-radius: 5px; padding: 8px 10px; background: #26313a; }
            QPushButton:hover { background: #31404b; }
            QSpinBox, QDoubleSpinBox, QComboBox { border: 1px solid #40505d; border-radius: 4px; padding: 5px; background: #101418; color: #e8eef4; }
            QLabel { color: #c8d1da; }
            """
        )

    def _config(self) -> Render3DConfig:
        duration = self.duration.value()
        if self.motion.keyframes and self.motion.duration > 0:
            duration = max(0.1, self.motion.duration)
            self.duration.setValue(duration)
        return Render3DConfig(
            shape=self.shape.currentText(),
            duration=duration,
            sample_rate=self.sample_rate.value(),
            scan_rate_hz=self.scan_rate_hz.value() if self.scan_rate_hz.value() > 0 else None,
            scan_note=self.scan_note.currentText().strip() or None,
            geometry_rate_hz=self.geometry_rate_hz.value(),
            scale=self.scale.value(),
            smoothing=self.smoothing.value(),
            normalize=self.normalize.isChecked(),
            invert_x=self.invert_x.isChecked(),
            invert_y=self.invert_y.isChecked(),
            projection=self.projection.currentText(),
            perspective=self.perspective.value(),
            view_scale=self.view_scale.value(),
            trace_mode=self.trace_mode.currentText(),
        )

    def _update_viewer_projection(self) -> None:
        self.viewer.set_projection(self.projection.currentText(), self.perspective.value(), self.view_scale.value())

    def select_primitive(self, name: str) -> None:
        self.custom_wireframe = None
        self.stl_path = None
        self.stl_settings_signature = None
        self.stl_status.setText("Primitive shape")
        self.viewer.set_shape(name)
        self._mark_render_dirty()

    def import_stl_dialog(self) -> None:
        path_text, _ = QFileDialog.getOpenFileName(self, "Import STL Wireframe", "", "STL files (*.stl)")
        if not path_text:
            return
        self._load_stl(Path(path_text))

    def reload_stl(self) -> None:
        if self.stl_path is None:
            self.statusBar().showMessage("No STL loaded")
            return
        self._load_stl(self.stl_path)

    def _load_stl(self, path: Path) -> None:
        try:
            wireframe = load_stl_wireframe(
                path,
                edge_mode=self.stl_edge_mode.currentText(),
                feature_angle_degrees=self.stl_feature_angle.value(),
                max_edges=self.stl_max_edges.value() or None,
            )
        except Exception as exc:
            QMessageBox.critical(self, "STL import failed", str(exc))
            return
        self.custom_wireframe = wireframe
        self.stl_path = path
        self.stl_settings_signature = self._stl_settings_signature()
        label = f"STL: {path.stem}"
        source_edges = wireframe.source_edge_count or len(wireframe.edges)
        self.stl_status.setText(
            f"{path.name} - {len(wireframe.vertices)} vertices, "
            f"{len(wireframe.edges)}/{source_edges} edges"
        )
        self.viewer.set_wireframe(wireframe, label)
        self._mark_render_dirty()
        self.statusBar().showMessage(f"Loaded STL for preview and WAV: {path}")

    def _stl_settings_signature(self) -> tuple[str, float, int | None]:
        return (
            self.stl_edge_mode.currentText(),
            round(float(self.stl_feature_angle.value()), 3),
            self.stl_max_edges.value() or None,
        )

    def _ensure_stl_settings_applied(self) -> bool:
        if self.stl_path is None:
            return True
        if self.stl_settings_signature == self._stl_settings_signature():
            return True
        self._load_stl(self.stl_path)
        return self.stl_settings_signature == self._stl_settings_signature()

    def _connect_render_dirty_signals(self) -> None:
        for combo in (self.shape, self.projection, self.trace_mode, self.scan_note, self.stl_edge_mode):
            combo.currentTextChanged.connect(self._mark_render_dirty)
        for spin in (
            self.perspective,
            self.view_scale,
            self.stl_feature_angle,
            self.stl_max_edges,
            self.duration,
            self.sample_rate,
            self.scan_rate_hz,
            self.geometry_rate_hz,
            self.scale,
            self.smoothing,
        ):
            spin.valueChanged.connect(self._mark_render_dirty)
        for checkbox in (self.normalize, self.invert_x, self.invert_y):
            checkbox.stateChanged.connect(self._mark_render_dirty)

    def _mark_render_dirty(self, *_args) -> None:
        if self.current_audio is None:
            return
        self.current_audio = None
        self.statusBar().showMessage("Settings changed; render will be rebuilt before playback/export")

    def on_transform_changed(self, transform: Transform) -> None:
        if self.recording:
            self.current_audio = None
            self.motion.add(transform)
            self.statusBar().showMessage(f"Recording movement: {self.motion.duration:.2f}s")

    def toggle_recording(self) -> None:
        if not self.recording:
            self.current_audio = None
            self.motion.start(self.viewer.transform)
            self.recording = True
            self.record_btn.setText("Stop Recording")
            self.statusBar().showMessage("Recording movement")
        else:
            duration = self.motion.stop(self.viewer.transform)
            self.recording = False
            self.record_btn.setText("Record Movement")
            self.duration.setValue(max(0.1, duration))
            self.statusBar().showMessage(f"Movement recorded: {duration:.2f}s")

    def stop_all(self) -> None:
        if self.recording:
            self.toggle_recording()
        winsound.PlaySound(None, winsound.SND_PURGE)
        self.statusBar().showMessage("Stopped")

    def reset(self) -> None:
        self.stop_all()
        self.motion.clear()
        self.current_audio = None
        self.viewer.reset_view()
        self.duration.setValue(5.0)
        self.statusBar().showMessage("Reset")

    def render_audio(self) -> None:
        self._start_render()

    def _start_render(self, export_path: str | None = None, play_after: bool = False) -> None:
        if self.render_thread is not None:
            self.statusBar().showMessage("Render already running")
            return
        try:
            if not self._ensure_stl_settings_applied():
                return
            config = self._config()
            motion = self.motion if self.motion.keyframes else None
        except Exception as exc:
            QMessageBox.critical(self, "3D render failed", str(exc))
            return

        self.render_export_path = export_path
        self.render_play_after = play_after
        self.render_thread = QThread(self)
        self.render_worker = RenderWorker(config, motion, self.custom_wireframe)
        self.render_worker.moveToThread(self.render_thread)
        self.render_thread.started.connect(self.render_worker.run)
        self.render_worker.finished.connect(self._render_finished)
        self.render_worker.failed.connect(self._render_failed)
        self.render_worker.finished.connect(self.render_thread.quit)
        self.render_worker.failed.connect(self.render_thread.quit)
        self.render_thread.finished.connect(self._render_thread_finished)
        self.render_worker.finished.connect(self.render_worker.deleteLater)
        self.render_worker.failed.connect(self.render_worker.deleteLater)
        self.render_thread.finished.connect(self.render_thread.deleteLater)
        self._set_render_busy(True)
        scan_label = config.scan_note or config.scan_rate_hz or 40
        self.statusBar().showMessage(
            f"Rendering audio in background: {config.duration:.2f}s, "
            f"{scan_label} scan, {config.geometry_rate_hz:.1f} geometry FPS"
        )
        self.render_thread.start()

    def _render_finished(self, result: object) -> None:
        audio, sample_rate = result
        self.current_audio = audio
        self.current_audio_sample_rate = int(sample_rate)
        if self.render_export_path:
            export_wav(self.current_audio, self.render_export_path, self.current_audio_sample_rate)
            self.statusBar().showMessage(f"WAV exported: {self.render_export_path}")
        else:
            self.statusBar().showMessage(f"Rendered {len(self.current_audio)} stereo samples")
        if self.render_play_after:
            self._play_current_audio()

    def _render_failed(self, message: str) -> None:
        QMessageBox.critical(self, "3D render failed", message)

    def _render_thread_finished(self) -> None:
        self.render_thread = None
        self.render_worker = None
        self.render_export_path = None
        self.render_play_after = False
        self._set_render_busy(False)

    def _set_render_busy(self, busy: bool) -> None:
        self.preview_btn.setEnabled(not busy)
        self.play_btn.setEnabled(not busy)
        self.export_btn.setEnabled(not busy)

    def play_xy(self) -> None:
        if self.current_audio is None:
            self._start_render(play_after=True)
            return
        self._play_current_audio()

    def _play_current_audio(self) -> None:
        if self.current_audio is None:
            return
        path = write_temp_wav(self.current_audio, self.current_audio_sample_rate)
        self.temp_playback_files.append(path)
        winsound.PlaySound(str(path), winsound.SND_FILENAME | winsound.SND_ASYNC)
        self.statusBar().showMessage("Playing generated 3D XY audio")

    def export_wav_dialog(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Export 3D WAV", "lissajou_3d.wav", "WAV files (*.wav)")
        if not path:
            return
        if self.current_audio is None:
            self._start_render(export_path=path)
            return
        export_wav(self.current_audio, path, self.current_audio_sample_rate)
        self.statusBar().showMessage(f"WAV exported: {path}")


def _spin(minimum: int, maximum: int, value: int, step: int) -> QSpinBox:
    box = QSpinBox()
    box.setRange(minimum, maximum)
    box.setValue(value)
    box.setSingleStep(step)
    box.setMinimumWidth(180)
    return box


def _double_spin(minimum: float, maximum: float, value: float, step: float) -> QDoubleSpinBox:
    box = QDoubleSpinBox()
    box.setRange(minimum, maximum)
    box.setValue(value)
    box.setSingleStep(step)
    box.setDecimals(3)
    box.setMinimumWidth(180)
    return box


def main() -> int:
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 9))
    window = MainWindow()
    window.show()
    return app.exec()
