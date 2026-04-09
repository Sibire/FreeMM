"""3D Digitizer Mode main widget.

Continuous probe scanning to build a 3D model with point cloud,
mesh generation, and parametric feature detection.
"""

import numpy as np
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QGroupBox, QComboBox, QFileDialog, QMessageBox, QCheckBox,
    QDoubleSpinBox, QSlider
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from .viewport_3d import Viewport3D
from .point_cloud import PointCloudManager
from .mesh_builder import build_mesh
from .feature_detect import detect_features
from diygitizer.export.ply_export import export_ply, export_points_csv
from diygitizer.export.stl_export import export_stl_binary
from diygitizer.export.step_export import export_features_step, _check_cadquery


class DigitizerWidget(QWidget):
    """Main 3D digitizer mode panel.

    Left: 3D viewport showing point cloud, mesh, features
    Right: Controls for scanning, processing, and export
    """

    def __init__(self, data_store, parent=None):
        super().__init__(parent)
        self.data_store = data_store
        self._scanning = False
        self._cloud = PointCloudManager()
        self._mesh_verts = None
        self._mesh_faces = None
        self._features = []
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        layout = QHBoxLayout(self)

        # Left: 3D Viewport
        self.viewport = Viewport3D()
        layout.addWidget(self.viewport, stretch=3)

        # Right: Controls
        controls = QWidget()
        controls.setMaximumWidth(280)
        ctrl_layout = QVBoxLayout(controls)

        # Scan controls
        scan_group = QGroupBox("Scan Controls")
        sl = QVBoxLayout(scan_group)

        self.scan_btn = QPushButton("Start Scanning")
        self.scan_btn.setMinimumHeight(40)
        self.scan_btn.clicked.connect(self._toggle_scanning)
        sl.addWidget(self.scan_btn)

        # Min distance
        dist_layout = QHBoxLayout()
        dist_layout.addWidget(QLabel("Min distance (mm):"))
        self.min_dist_spin = QDoubleSpinBox()
        self.min_dist_spin.setRange(0.1, 10.0)
        self.min_dist_spin.setValue(0.5)
        self.min_dist_spin.setSingleStep(0.1)
        self.min_dist_spin.valueChanged.connect(self._on_min_dist_changed)
        dist_layout.addWidget(self.min_dist_spin)
        sl.addLayout(dist_layout)

        self.point_count_label = QLabel("Points: 0")
        sl.addWidget(self.point_count_label)

        # Point size slider
        size_layout = QHBoxLayout()
        size_layout.addWidget(QLabel("Point size:"))
        self.size_slider = QSlider(Qt.Horizontal)
        self.size_slider.setRange(1, 10)
        self.size_slider.setValue(3)
        self.size_slider.valueChanged.connect(
            lambda v: setattr(self.viewport, 'point_size', float(v)) or self.viewport.update()
        )
        size_layout.addWidget(self.size_slider)
        sl.addLayout(size_layout)

        ctrl_layout.addWidget(scan_group)

        # Processing
        proc_group = QGroupBox("Processing")
        pl = QVBoxLayout(proc_group)

        # Mesh generation
        self.mesh_btn = QPushButton("Generate Mesh")
        self.mesh_btn.setMinimumHeight(35)
        self.mesh_btn.clicked.connect(self._generate_mesh)
        self.mesh_btn.setEnabled(False)
        pl.addWidget(self.mesh_btn)

        mesh_method_layout = QHBoxLayout()
        mesh_method_layout.addWidget(QLabel("Method:"))
        self.mesh_method = QComboBox()
        self.mesh_method.addItems(["Poisson", "Ball Pivoting", "Delaunay (fallback)"])
        mesh_method_layout.addWidget(self.mesh_method)
        pl.addLayout(mesh_method_layout)

        # Feature detection
        self.detect_btn = QPushButton("Detect Features")
        self.detect_btn.setMinimumHeight(35)
        self.detect_btn.clicked.connect(self._detect_features)
        self.detect_btn.setEnabled(False)
        pl.addWidget(self.detect_btn)

        self.feature_label = QLabel("Features: --")
        pl.addWidget(self.feature_label)

        ctrl_layout.addWidget(proc_group)

        # Export
        export_group = QGroupBox("Export")
        el = QVBoxLayout(export_group)

        self.export_ply_btn = QPushButton("Export Point Cloud (PLY)")
        self.export_ply_btn.clicked.connect(self._export_ply)
        self.export_ply_btn.setEnabled(False)
        el.addWidget(self.export_ply_btn)

        self.export_csv_btn = QPushButton("Export Point Cloud (CSV)")
        self.export_csv_btn.clicked.connect(self._export_csv)
        self.export_csv_btn.setEnabled(False)
        el.addWidget(self.export_csv_btn)

        self.export_stl_btn = QPushButton("Export Mesh (STL)")
        self.export_stl_btn.clicked.connect(self._export_stl)
        self.export_stl_btn.setEnabled(False)
        el.addWidget(self.export_stl_btn)

        self.export_step_btn = QPushButton("Export Parametric (STEP)")
        self.export_step_btn.clicked.connect(self._export_step)
        self.export_step_btn.setEnabled(False)
        if not _check_cadquery():
            self.export_step_btn.setToolTip(
                "Install CadQuery for STEP export: pip install cadquery"
            )
        el.addWidget(self.export_step_btn)

        ctrl_layout.addWidget(export_group)

        # Clear
        self.clear_btn = QPushButton("Clear Scan")
        self.clear_btn.clicked.connect(self._clear)
        ctrl_layout.addWidget(self.clear_btn)

        ctrl_layout.addStretch()
        layout.addWidget(controls)

    def _connect_signals(self):
        self.data_store.arm_state_changed.connect(self._on_arm_state)
        self.data_store.settings_changed.connect(self._on_settings_changed)

    def _on_arm_state(self, arm_state):
        """Handle arm state update — add point if scanning."""
        # Update arm visualization
        if arm_state.joint_positions:
            self.viewport.set_arm_joints(arm_state.joint_positions)

        if self._scanning:
            added = self._cloud.add_point(
                arm_state.tip_x, arm_state.tip_y, arm_state.tip_z
            )
            if added:
                count = self._cloud.get_point_count()
                self.point_count_label.setText(f"Points: {count}")
                # Update viewport periodically
                if count % 5 == 0:
                    self.viewport.set_point_cloud(self._cloud.get_points())

    def _toggle_scanning(self):
        if self._scanning:
            self._stop_scanning()
        else:
            self._start_scanning()

    def _start_scanning(self):
        self._scanning = True
        self.scan_btn.setText("Stop Scanning")
        self._cloud.min_distance = self.min_dist_spin.value()
        self._cloud.ball_radius = self.data_store.settings.ball_radius

    def _stop_scanning(self):
        self._scanning = False
        self.scan_btn.setText("Start Scanning")

        count = self._cloud.get_point_count()
        if count > 0:
            self.viewport.set_point_cloud(self._cloud.get_points())
            self.mesh_btn.setEnabled(count >= 10)
            self.detect_btn.setEnabled(count >= 20)
            self.export_ply_btn.setEnabled(True)
            self.export_csv_btn.setEnabled(True)

    def _generate_mesh(self):
        points = self._cloud.get_points()
        if len(points) < 10:
            QMessageBox.information(self, "Insufficient Data",
                                    "Need at least 10 points for mesh.")
            return

        method_map = {
            "Poisson": "poisson",
            "Ball Pivoting": "ball_pivoting",
            "Delaunay (fallback)": "delaunay",
        }
        method = method_map.get(self.mesh_method.currentText(), "poisson")

        try:
            self._mesh_verts, self._mesh_faces = build_mesh(points, method=method)
            self.viewport.set_mesh(self._mesh_verts, self._mesh_faces)
            self.export_stl_btn.setEnabled(True)

            n_faces = len(self._mesh_faces) if self._mesh_faces is not None else 0
            QMessageBox.information(self, "Mesh Generated",
                                    f"Generated mesh with {n_faces} triangles.")
        except Exception as e:
            QMessageBox.warning(self, "Mesh Error", str(e))

    def _detect_features(self):
        points = self._cloud.get_points()
        if len(points) < 20:
            QMessageBox.information(self, "Insufficient Data",
                                    "Need at least 20 points for feature detection.")
            return

        rounding = self.data_store.settings.rounding_precision

        try:
            self._features = detect_features(points, rounding=rounding)
            self.viewport.set_features(self._features)
            self.viewport.set_rounding(rounding)

            counts = {}
            for f in self._features:
                counts[f['type']] = counts.get(f['type'], 0) + 1
            summary = ", ".join(f"{v} {k}" for k, v in counts.items())
            self.feature_label.setText(
                f"Features: {summary}" if summary else "Features: none detected"
            )

            self.export_step_btn.setEnabled(
                len(self._features) > 0 and _check_cadquery()
            )
        except Exception as e:
            QMessageBox.warning(self, "Detection Error", str(e))

    def _export_ply(self):
        points = self._cloud.get_points()
        if len(points) == 0:
            return

        filepath, _ = QFileDialog.getSaveFileName(
            self, "Export PLY", "scan.ply", "PLY Files (*.ply)"
        )
        if filepath:
            export_ply(points, filepath)

    def _export_csv(self):
        points = self._cloud.get_points()
        if len(points) == 0:
            return

        filepath, _ = QFileDialog.getSaveFileName(
            self, "Export CSV", "scan.csv", "CSV Files (*.csv)"
        )
        if filepath:
            export_points_csv(points, filepath)

    def _export_stl(self):
        if self._mesh_verts is None or self._mesh_faces is None:
            QMessageBox.information(self, "No Mesh",
                                    "Generate a mesh first.")
            return

        filepath, _ = QFileDialog.getSaveFileName(
            self, "Export STL", "scan.stl", "STL Files (*.stl)"
        )
        if filepath:
            export_stl_binary(self._mesh_verts, self._mesh_faces, filepath)

    def _export_step(self):
        if not self._features:
            QMessageBox.information(self, "No Features",
                                    "Detect features first.")
            return

        filepath, _ = QFileDialog.getSaveFileName(
            self, "Export STEP", "scan.step", "STEP Files (*.step *.stp)"
        )
        if filepath:
            try:
                rounding = self.data_store.settings.rounding_precision
                export_features_step(self._features, filepath, rounding)
                QMessageBox.information(self, "Exported",
                                        f"STEP saved to {filepath}")
            except ImportError as e:
                QMessageBox.warning(self, "CadQuery Required", str(e))
            except Exception as e:
                QMessageBox.warning(self, "Export Error", str(e))

    def _clear(self):
        self._scanning = False
        self._cloud.clear()
        self._mesh_verts = None
        self._mesh_faces = None
        self._features = []
        self.viewport.clear_all()
        self.scan_btn.setText("Start Scanning")
        self.point_count_label.setText("Points: 0")
        self.feature_label.setText("Features: --")
        self.mesh_btn.setEnabled(False)
        self.detect_btn.setEnabled(False)
        self.export_ply_btn.setEnabled(False)
        self.export_csv_btn.setEnabled(False)
        self.export_stl_btn.setEnabled(False)
        self.export_step_btn.setEnabled(False)

    def _on_min_dist_changed(self, val):
        self._cloud.min_distance = val

    def _on_settings_changed(self):
        self._cloud.ball_radius = self.data_store.settings.ball_radius
        self.viewport.set_rounding(self.data_store.settings.rounding_precision)
