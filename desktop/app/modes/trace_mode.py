"""2D Trace Mode — trace outlines, process through geometry pipeline, export."""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QGroupBox,
    QComboBox, QSpinBox, QDoubleSpinBox, QCheckBox, QFileDialog,
    QMessageBox, QSplitter
)
from PyQt5.QtCore import Qt
import numpy as np

from app.viewers.viewer_2d import TraceViewer
from app.geometry.trace_pipeline import run_pipeline


class TraceMode(QWidget):
    def __init__(self, state):
        super().__init__()
        self.state = state
        self._pipeline_result = None
        self._build_ui()
        self._connect_signals()

    def _build_ui(self):
        layout = QHBoxLayout(self)

        # Left: 2D viewer
        self.viewer = TraceViewer()
        layout.addWidget(self.viewer, stretch=3)

        # Right: controls
        controls = QWidget()
        controls.setFixedWidth(280)
        ctrl_layout = QVBoxLayout(controls)

        # Trace controls
        trace_group = QGroupBox("Trace Controls")
        tl = QVBoxLayout(trace_group)

        plane_row = QHBoxLayout()
        plane_row.addWidget(QLabel("Plane:"))
        self.plane_combo = QComboBox()
        self.plane_combo.addItems(["XZ (side)", "XY (top)", "YZ (front)"])
        plane_row.addWidget(self.plane_combo)
        tl.addLayout(plane_row)

        self.lbl_status = QLabel("Status: Idle")
        tl.addWidget(self.lbl_status)

        self.lbl_count = QLabel("Points: 0")
        tl.addWidget(self.lbl_count)

        btn_row = QHBoxLayout()
        self.btn_clear = QPushButton("Clear Trace")
        self.btn_clear.clicked.connect(self._clear_trace)
        btn_row.addWidget(self.btn_clear)
        tl.addLayout(btn_row)

        ctrl_layout.addWidget(trace_group)

        # Pipeline settings
        pipe_group = QGroupBox("Pipeline Settings")
        pl = QVBoxLayout(pipe_group)

        self.chk_compensate = QCheckBox("Probe Compensation")
        self.chk_compensate.setChecked(True)
        pl.addWidget(self.chk_compensate)

        smooth_row = QHBoxLayout()
        smooth_row.addWidget(QLabel("Smooth Window:"))
        self.spin_smooth = QSpinBox()
        self.spin_smooth.setRange(1, 21)
        self.spin_smooth.setValue(5)
        self.spin_smooth.setSingleStep(2)
        smooth_row.addWidget(self.spin_smooth)
        pl.addLayout(smooth_row)

        simp_row = QHBoxLayout()
        simp_row.addWidget(QLabel("Simplify (mm):"))
        self.spin_simplify = QDoubleSpinBox()
        self.spin_simplify.setRange(0.1, 10.0)
        self.spin_simplify.setValue(0.5)
        self.spin_simplify.setSingleStep(0.1)
        simp_row.addWidget(self.spin_simplify)
        pl.addLayout(simp_row)

        thresh_row = QHBoxLayout()
        thresh_row.addWidget(QLabel("Fit Threshold (mm):"))
        self.spin_threshold = QDoubleSpinBox()
        self.spin_threshold.setRange(0.1, 10.0)
        self.spin_threshold.setValue(1.0)
        self.spin_threshold.setSingleStep(0.1)
        thresh_row.addWidget(self.spin_threshold)
        pl.addLayout(thresh_row)

        self.btn_process = QPushButton("Process Trace")
        self.btn_process.clicked.connect(self._process_trace)
        pl.addWidget(self.btn_process)

        ctrl_layout.addWidget(pipe_group)

        # Export
        export_group = QGroupBox("Export")
        el = QVBoxLayout(export_group)

        self.btn_export_dxf = QPushButton("Export DXF")
        self.btn_export_dxf.clicked.connect(self._export_dxf)
        el.addWidget(self.btn_export_dxf)

        self.btn_export_svg = QPushButton("Export SVG")
        self.btn_export_svg.clicked.connect(self._export_svg)
        el.addWidget(self.btn_export_svg)

        self.btn_fit = QPushButton("Fit View")
        self.btn_fit.clicked.connect(self.viewer.fit_to_content)
        el.addWidget(self.btn_fit)

        ctrl_layout.addWidget(export_group)

        # Feature list
        self.lbl_features = QLabel("Features: —")
        self.lbl_features.setWordWrap(True)
        ctrl_layout.addWidget(self.lbl_features)

        ctrl_layout.addStretch()
        layout.addWidget(controls)

    def _connect_signals(self):
        self.state.trace_point_added.connect(self._on_trace_point)
        self.state.trace_started.connect(self._on_trace_started)
        self.state.trace_stopped.connect(self._on_trace_stopped)
        self.state.traces_cleared.connect(self._on_traces_cleared)

    def _on_trace_point(self, idx, a, b):
        self.lbl_count.setText(f"Points: {len(self.state.trace_points)}")

    def _on_trace_started(self, plane):
        self.lbl_status.setText(f"Status: Tracing ({plane})")

    def _on_trace_stopped(self):
        self.lbl_status.setText("Status: Trace complete")

    def _on_traces_cleared(self):
        self.viewer.clear_all()
        self.lbl_count.setText("Points: 0")
        self.lbl_status.setText("Status: Idle")
        self.lbl_features.setText("Features: —")
        self._pipeline_result = None

    def _clear_trace(self):
        self.state.clear_traces()

    def _process_trace(self):
        if not self.state.trace_points:
            QMessageBox.information(self, "Process", "No trace data to process.")
            return

        # Extract 2D coordinates
        raw_pts = [(a, b) for _, a, b in self.state.trace_points]

        result = run_pipeline(
            raw_pts,
            compensate=self.chk_compensate.isChecked(),
            ball_radius=0.5,
            smooth_window=self.spin_smooth.value(),
            simplify_epsilon=self.spin_simplify.value(),
            line_threshold=self.spin_threshold.value(),
            arc_threshold=self.spin_threshold.value(),
        )
        self._pipeline_result = result

        # Update viewer
        self.viewer.set_raw_points(raw_pts)
        self.viewer.set_features(result['features'])
        self.viewer.set_dimensions(result['dimensions'])
        self.viewer.fit_to_content()

        # Update feature summary
        feat_types = [f['type'] for f in result['features']]
        summary_parts = []
        for ft in ['LINE', 'ARC', 'CIRCLE']:
            count = feat_types.count(ft)
            if count:
                summary_parts.append(f"{count} {ft}")
        self.lbl_features.setText(f"Features: {', '.join(summary_parts) or 'None detected'}")

    def _export_dxf(self):
        if not self._pipeline_result or not self._pipeline_result['features']:
            QMessageBox.information(self, "Export", "Process trace first.")
            return

        path, _ = QFileDialog.getSaveFileName(self, "Export DXF", "trace.dxf",
                                               "DXF Files (*.dxf)")
        if not path:
            return

        from app.export.dxf_export import export_trace_dxf
        export_trace_dxf(path, self._pipeline_result)
        QMessageBox.information(self, "Export", f"DXF saved to {path}")

    def _export_svg(self):
        if not self._pipeline_result or not self._pipeline_result['features']:
            QMessageBox.information(self, "Export", "Process trace first.")
            return

        path, _ = QFileDialog.getSaveFileName(self, "Export SVG", "trace.svg",
                                               "SVG Files (*.svg)")
        if not path:
            return

        from app.export.svg_export import export_trace_svg
        export_trace_svg(path, self._pipeline_result)
        QMessageBox.information(self, "Export", f"SVG saved to {path}")
