"""2D Trace Mode main widget.

Captures 2D outlines and processes them through the geometry pipeline
to produce dimensioned drawings for export.
"""

import numpy as np
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QSplitter, QGroupBox, QComboBox, QFileDialog, QMessageBox,
    QCheckBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from .canvas_2d import Canvas2D
from .geometry_pipeline import run_pipeline
from diygitizer.models.trace import TraceSession
from diygitizer.export.dxf_export import export_trace_dxf
from diygitizer.export.svg_export import export_trace_svg


class TraceWidget(QWidget):
    """Main 2D trace mode panel.

    Left: 2D canvas showing raw trace + fitted features with dimensions
    Right: Controls for tracing, processing, and export
    """

    def __init__(self, data_store, parent=None):
        super().__init__(parent)
        self.data_store = data_store
        self._trace_active = False
        self._raw_points = []
        self._pipeline_result = None
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        layout = QHBoxLayout(self)

        # Left: Canvas
        self.canvas = Canvas2D()
        layout.addWidget(self.canvas, stretch=3)

        # Right: Controls
        controls = QWidget()
        controls.setMaximumWidth(280)
        ctrl_layout = QVBoxLayout(controls)

        # Trace controls
        trace_group = QGroupBox("Trace Controls")
        tl = QVBoxLayout(trace_group)

        # Plane selector
        plane_layout = QHBoxLayout()
        plane_layout.addWidget(QLabel("Plane:"))
        self.plane_combo = QComboBox()
        self.plane_combo.addItems(["XY", "XZ", "YZ"])
        self.plane_combo.setCurrentText("XY")
        plane_layout.addWidget(self.plane_combo)
        tl.addLayout(plane_layout)

        # Compensate checkbox
        self.compensate_check = QCheckBox("Probe compensation (0.5mm)")
        self.compensate_check.setChecked(True)
        tl.addWidget(self.compensate_check)

        # Start/Stop trace
        self.trace_btn = QPushButton("Start Trace")
        self.trace_btn.setMinimumHeight(40)
        self.trace_btn.clicked.connect(self._toggle_trace)
        tl.addWidget(self.trace_btn)

        self.point_count_label = QLabel("Points: 0")
        tl.addWidget(self.point_count_label)

        ctrl_layout.addWidget(trace_group)

        # Processing
        proc_group = QGroupBox("Processing")
        pl = QVBoxLayout(proc_group)

        self.process_btn = QPushButton("Run Pipeline")
        self.process_btn.setMinimumHeight(35)
        self.process_btn.setToolTip(
            "Process trace: smooth → compensate → simplify → detect features"
        )
        self.process_btn.clicked.connect(self._run_pipeline)
        self.process_btn.setEnabled(False)
        pl.addWidget(self.process_btn)

        self.feature_label = QLabel("Features: --")
        pl.addWidget(self.feature_label)

        ctrl_layout.addWidget(proc_group)

        # Export
        export_group = QGroupBox("Export")
        el = QVBoxLayout(export_group)

        self.export_dxf_btn = QPushButton("Export DXF")
        self.export_dxf_btn.clicked.connect(self._export_dxf)
        self.export_dxf_btn.setEnabled(False)
        el.addWidget(self.export_dxf_btn)

        self.export_svg_btn = QPushButton("Export SVG")
        self.export_svg_btn.clicked.connect(self._export_svg)
        self.export_svg_btn.setEnabled(False)
        el.addWidget(self.export_svg_btn)

        ctrl_layout.addWidget(export_group)

        # Clear
        self.clear_btn = QPushButton("Clear Trace")
        self.clear_btn.clicked.connect(self._clear)
        ctrl_layout.addWidget(self.clear_btn)

        ctrl_layout.addStretch()
        layout.addWidget(controls)

    def _connect_signals(self):
        self.data_store.trace_point_added.connect(self._on_trace_point)
        self.data_store.settings_changed.connect(self._on_settings_changed)

    def _toggle_trace(self):
        if self._trace_active:
            self._stop_trace()
        else:
            self._start_trace()

    def _start_trace(self):
        self._trace_active = True
        self._raw_points = []
        self.trace_btn.setText("Stop Trace")
        self.process_btn.setEnabled(False)
        self.export_dxf_btn.setEnabled(False)
        self.export_svg_btn.setEnabled(False)
        self.canvas.clear()

        # Send trace start command to connection
        if hasattr(self.data_store, '_connection') and self.data_store._connection:
            plane_map = {"XY": "1", "XZ": "2", "YZ": "3"}
            plane_cmd = plane_map.get(self.plane_combo.currentText(), "1")
            self.data_store._connection.write(plane_cmd)
            self.data_store._connection.write("t")

    def _stop_trace(self):
        self._trace_active = False
        self.trace_btn.setText("Start Trace")

        if hasattr(self.data_store, '_connection') and self.data_store._connection:
            self.data_store._connection.write("t")

        if len(self._raw_points) >= 3:
            self.process_btn.setEnabled(True)
            raw = np.array(self._raw_points)
            self.canvas.set_raw_points(raw)

    def _on_trace_point(self, data):
        """Handle trace point from hardware/simulator."""
        if not self._trace_active:
            return

        if hasattr(data, '__len__') and len(data) >= 3:
            # data is (idx, a, b)
            _, a, b = data[0], data[1], data[2]
        else:
            return

        self._raw_points.append([a, b])
        self.point_count_label.setText(f"Points: {len(self._raw_points)}")

        # Live update canvas every 10 points
        if len(self._raw_points) % 10 == 0:
            raw = np.array(self._raw_points)
            self.canvas.set_raw_points(raw)

    def _capture_trace_from_arm(self):
        """Alternative: capture trace from continuous arm position."""
        if not self._trace_active:
            return

        state = self.data_store.arm_state
        plane = self.plane_combo.currentText()

        if plane == "XY":
            a, b = state.tip_x, state.tip_y
        elif plane == "XZ":
            a, b = state.tip_x, state.tip_z
        else:  # YZ
            a, b = state.tip_y, state.tip_z

        # Min distance check
        min_dist = self.data_store.settings.trace_min_dist
        if self._raw_points:
            last = self._raw_points[-1]
            dx = a - last[0]
            dy = b - last[1]
            if (dx * dx + dy * dy) < min_dist * min_dist:
                return

        self._raw_points.append([a, b])
        self.point_count_label.setText(f"Points: {len(self._raw_points)}")

    def _run_pipeline(self):
        """Run the geometry processing pipeline on captured trace."""
        if len(self._raw_points) < 3:
            QMessageBox.information(self, "Insufficient Data",
                                    "Need at least 3 points to process.")
            return

        raw = np.array(self._raw_points)
        settings = self.data_store.settings
        ball_r = settings.ball_radius if self.compensate_check.isChecked() else 0

        self._pipeline_result = run_pipeline(
            raw,
            ball_radius=ball_r,
            rounding=settings.rounding_precision,
        )

        features = self._pipeline_result['features']
        self.canvas.set_features(features)
        self.canvas.set_rounding(settings.rounding_precision)

        # Update feature summary
        counts = {}
        for f in features:
            counts[f['type']] = counts.get(f['type'], 0) + 1
        summary = ", ".join(f"{v} {k}" for k, v in counts.items())
        self.feature_label.setText(f"Features: {summary}" if summary else "Features: none detected")

        self.export_dxf_btn.setEnabled(len(features) > 0)
        self.export_svg_btn.setEnabled(len(features) > 0)

        # Store trace session
        session = TraceSession(
            plane=self.plane_combo.currentText(),
            points=self._raw_points.copy(),
            features=features,
        )
        self.data_store.traces.append(session)

    def _export_dxf(self):
        if not self._pipeline_result or not self._pipeline_result['features']:
            return

        filepath, _ = QFileDialog.getSaveFileName(
            self, "Export DXF", "trace.dxf", "DXF Files (*.dxf)"
        )
        if filepath:
            export_trace_dxf(
                self._pipeline_result['features'],
                filepath,
                rounding=self.data_store.settings.rounding_precision,
            )
            QMessageBox.information(self, "Exported",
                                    f"DXF saved to {filepath}")

    def _export_svg(self):
        if not self._pipeline_result or not self._pipeline_result['features']:
            return

        filepath, _ = QFileDialog.getSaveFileName(
            self, "Export SVG", "trace.svg", "SVG Files (*.svg)"
        )
        if filepath:
            export_trace_svg(
                self._pipeline_result['features'],
                filepath,
                rounding=self.data_store.settings.rounding_precision,
            )
            QMessageBox.information(self, "Exported",
                                    f"SVG saved to {filepath}")

    def _clear(self):
        self._trace_active = False
        self._raw_points = []
        self._pipeline_result = None
        self.canvas.clear()
        self.trace_btn.setText("Start Trace")
        self.point_count_label.setText("Points: 0")
        self.feature_label.setText("Features: --")
        self.process_btn.setEnabled(False)
        self.export_dxf_btn.setEnabled(False)
        self.export_svg_btn.setEnabled(False)

    def _on_settings_changed(self):
        self.canvas.set_rounding(self.data_store.settings.rounding_precision)
        if self.compensate_check.isChecked():
            self.compensate_check.setText(
                f"Probe compensation ({self.data_store.settings.ball_radius}mm)"
            )
