from __future__ import annotations

from pathlib import Path
import sys
import winsound

import numpy as np
from PyQt6.QtCore import QPoint, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPalette, QPen
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
from .geometry import Transform, make_shape, project_wireframe
from .motion import MotionTrack, copy_transform
from .render import Render3DConfig, build_3d_xy_audio


class WireframeViewer(QOpenGLWidget):
    transform_changed = pyqtSignal(object)

    def __init__(self) -> None:
        super().__init__()
        self.shape_name = "cube"
        self.projection = "orthographic"
        self.perspective = 2.8
        self.view_scale = 2.4
        self.transform = Transform(rotation_x=25.0, rotation_y=-30.0, rotation_z=0.0, zoom=1.0)
        self._last_pos: QPoint | None = None
        self.setMinimumSize(520, 420)
        self.setMouseTracking(True)

    def set_shape(self, name: str) -> None:
        self.shape_name = name
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

    def paintGL(self) -> None:  # noqa: N802 - Qt naming
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#101418"))

        side = min(self.width(), self.height()) - 48
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
            contours = project_wireframe(
                make_shape(self.shape_name),
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
        painter.drawText(16, 24, f"{self.shape_name} - drag to rotate, wheel to zoom, right-drag to move")
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


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Lissajou3D")
        self.resize(1180, 760)
        self.motion = MotionTrack()
        self.recording = False
        self.current_audio: np.ndarray | None = None
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
        self.projection = QComboBox()
        self.projection.addItems(["orthographic", "perspective"])
        self.perspective = _double_spin(0.001, 1_000_000.0, 2.8, 0.1)
        self.view_scale = _double_spin(0.001, 1_000_000.0, 2.4, 0.1)
        self.trace_mode = QComboBox()
        self.trace_mode.addItems(["wire_walk", "fast_jumps"])
        shape_form.addRow("Shape", self.shape)
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
        preview_btn = QPushButton("Render Preview")
        preview_btn.clicked.connect(self.render_audio)
        play_btn = QPushButton("Play XY")
        play_btn.clicked.connect(self.play_xy)
        export_btn = QPushButton("Export WAV")
        export_btn.clicked.connect(self.export_wav_dialog)
        action_row.addWidget(preview_btn)
        action_row.addWidget(play_btn)
        action_row.addWidget(export_btn)
        controls_layout.addLayout(action_row)
        controls_layout.addStretch(1)

        self.viewer = WireframeViewer()
        self.viewer.transform_changed.connect(self.on_transform_changed)
        self.shape.currentTextChanged.connect(self.viewer.set_shape)
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

    def _connect_render_dirty_signals(self) -> None:
        for combo in (self.shape, self.projection, self.trace_mode, self.scan_note):
            combo.currentTextChanged.connect(self._mark_render_dirty)
        for spin in (
            self.perspective,
            self.view_scale,
            self.duration,
            self.sample_rate,
            self.scan_rate_hz,
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
        try:
            config = self._config()
            motion = self.motion if self.motion.keyframes else None
            self.current_audio = build_3d_xy_audio(config, motion=motion)
        except Exception as exc:
            QMessageBox.critical(self, "3D render failed", str(exc))
            return
        self.statusBar().showMessage(f"Rendered {len(self.current_audio)} stereo samples")

    def play_xy(self) -> None:
        if self.current_audio is None:
            self.render_audio()
        if self.current_audio is None:
            return
        path = write_temp_wav(self.current_audio, self._config().sample_rate)
        self.temp_playback_files.append(path)
        winsound.PlaySound(str(path), winsound.SND_FILENAME | winsound.SND_ASYNC)
        self.statusBar().showMessage("Playing generated 3D XY audio")

    def export_wav_dialog(self) -> None:
        if self.current_audio is None:
            self.render_audio()
        if self.current_audio is None:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export 3D WAV", "lissajou_3d.wav", "WAV files (*.wav)")
        if not path:
            return
        export_wav(self.current_audio, path, self._config().sample_rate)
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
