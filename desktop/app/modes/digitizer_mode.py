"""3D Digitizer Mode — continuous scanning, 3D preview, mesh/parametric export."""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QGroupBox,
    QComboBox, QSpinBox, QDoubleSpinBox, QFileDialog, QMessageBox
)
from PyQt5.QtCore import Qt
import numpy as np

from app.viewers.viewer_3d import Viewer3D


class DigitizerMode(QWidget):
    def __init__(self, state):
        super().__init__()
        self.state = state
        self._mesh_verts = None
        self._mesh_faces = None
        self._features = []
        self._build_ui()
        self._connect_signals()

    def _build_ui(self):
        layout = QHBoxLayout(self)

        # Left: 3D viewer
        self.viewer = Viewer3D()
        layout.addWidget(self.viewer, stretch=3)

        # Right: controls
        controls = QWidget()
        controls.setFixedWidth(280)
        ctrl_layout = QVBoxLayout(controls)

        # Scan controls
        scan_group = QGroupBox("Scan Controls")
        sl = QVBoxLayout(scan_group)

        self.lbl_status = QLabel("Status: Idle")
        sl.addWidget(self.lbl_status)

        self.lbl_count = QLabel("Points: 0")
        sl.addWidget(self.lbl_count)

        btn_row = QHBoxLayout()
        self.btn_start = QPushButton("Start Scan")
        self.btn_start.clicked.connect(self._toggle_scan)
        self.btn_clear = QPushButton("Clear")
        self.btn_clear.clicked.connect(self._clear_scan)
        btn_row.addWidget(self.btn_start)
        btn_row.addWidget(self.btn_clear)
        sl.addLayout(btn_row)

        ctrl_layout.addWidget(scan_group)

        # Mesh generation
        mesh_group = QGroupBox("Mesh Generation")
        ml = QVBoxLayout(mesh_group)

        method_row = QHBoxLayout()
        method_row.addWidget(QLabel("Method:"))
        self.mesh_combo = QComboBox()
        self.mesh_combo.addItems(["Delaunay (fast)", "Ball Pivot", "Poisson (best)"])
        method_row.addWidget(self.mesh_combo)
        ml.addLayout(method_row)

        self.btn_gen_mesh = QPushButton("Generate Mesh")
        self.btn_gen_mesh.clicked.connect(self._generate_mesh)
        ml.addWidget(self.btn_gen_mesh)

        self.lbl_mesh = QLabel("Mesh: —")
        ml.addWidget(self.lbl_mesh)

        ctrl_layout.addWidget(mesh_group)

        # Feature detection
        feat_group = QGroupBox("Feature Detection")
        fl = QVBoxLayout(feat_group)

        thresh_row = QHBoxLayout()
        thresh_row.addWidget(QLabel("Threshold (mm):"))
        self.spin_threshold = QDoubleSpinBox()
        self.spin_threshold.setRange(0.5, 10.0)
        self.spin_threshold.setValue(2.0)
        self.spin_threshold.setSingleStep(0.5)
        thresh_row.addWidget(self.spin_threshold)
        fl.addLayout(thresh_row)

        self.btn_detect = QPushButton("Detect Features")
        self.btn_detect.clicked.connect(self._detect_features)
        fl.addWidget(self.btn_detect)

        self.lbl_features = QLabel("Features: —")
        self.lbl_features.setWordWrap(True)
        fl.addWidget(self.lbl_features)

        ctrl_layout.addWidget(feat_group)

        # Export
        export_group = QGroupBox("Export")
        el = QVBoxLayout(export_group)

        self.btn_export_ply = QPushButton("Export Point Cloud (PLY)")
        self.btn_export_ply.clicked.connect(self._export_ply)
        el.addWidget(self.btn_export_ply)

        self.btn_export_csv = QPushButton("Export Points (CSV)")
        self.btn_export_csv.clicked.connect(self._export_csv)
        el.addWidget(self.btn_export_csv)

        self.btn_export_stl = QPushButton("Export Mesh (STL)")
        self.btn_export_stl.clicked.connect(self._export_stl)
        el.addWidget(self.btn_export_stl)

        self.btn_export_step = QPushButton("Export Parametric (STEP)")
        self.btn_export_step.clicked.connect(self._export_step)
        el.addWidget(self.btn_export_step)

        ctrl_layout.addWidget(export_group)

        ctrl_layout.addStretch()
        layout.addWidget(controls)

    def _connect_signals(self):
        self.state.point_added.connect(self._on_point)
        self.state.position_updated.connect(self._on_position)

    def _on_point(self, idx, pt):
        if self.state.scanning:
            self.viewer.add_point(pt.tolist())
            self.lbl_count.setText(f"Points: {len(self.state.scan_points)}")

    def _on_position(self, pos):
        # Update arm wireframe in 3D view
        if self.state.joint_positions:
            self.viewer.set_arm_joints(self.state.joint_positions)

    def _toggle_scan(self):
        if self.state.scanning:
            self.state.stop_scan()
            self.btn_start.setText("Start Scan")
            self.lbl_status.setText("Status: Stopped")
        else:
            self.state.start_scan()
            self.btn_start.setText("Stop Scan")
            self.lbl_status.setText("Status: Scanning...")

    def _clear_scan(self):
        self.state.clear_scan()
        self.viewer.clear_all()
        self._mesh_verts = None
        self._mesh_faces = None
        self._features = []
        self.lbl_count.setText("Points: 0")
        self.lbl_mesh.setText("Mesh: —")
        self.lbl_features.setText("Features: —")
        self.lbl_status.setText("Status: Idle")

    def _generate_mesh(self):
        if not self.state.scan_points:
            QMessageBox.information(self, "Mesh", "No scan points. Start scanning first.")
            return

        pts = np.array(self.state.scan_points)
        method = self.mesh_combo.currentIndex()

        from app.geometry.mesh import (
            points_to_mesh_delaunay,
            points_to_mesh_ball_pivot,
            points_to_mesh_poisson,
        )

        if method == 0:
            verts, faces = points_to_mesh_delaunay(pts)
        elif method == 1:
            verts, faces = points_to_mesh_ball_pivot(pts)
        else:
            verts, faces = points_to_mesh_poisson(pts)

        if len(faces) == 0:
            QMessageBox.warning(self, "Mesh", "Could not generate mesh. Try more points.")
            return

        self._mesh_verts = verts
        self._mesh_faces = faces
        self.viewer.set_mesh(verts, faces)
        self.lbl_mesh.setText(f"Mesh: {len(verts)} verts, {len(faces)} faces")

    def _detect_features(self):
        if not self.state.scan_points:
            QMessageBox.information(self, "Features", "No scan points.")
            return

        pts = np.array(self.state.scan_points)
        from app.geometry.features_3d import detect_features_3d
        features = detect_features_3d(pts, threshold=self.spin_threshold.value())

        self._features = features
        self.viewer.set_features_3d(features)

        if features:
            parts = []
            for f in features:
                ftype = f['type']
                if ftype == 'PLANE':
                    parts.append(f"Plane ({f['inlier_count']} pts)")
                elif ftype == 'SPHERE':
                    parts.append(f"Sphere R={f['radius']:.1f} ({f['inlier_count']} pts)")
                elif ftype == 'CYLINDER':
                    parts.append(f"Cylinder R={f['radius']:.1f} ({f['inlier_count']} pts)")
            self.lbl_features.setText(f"Features: {', '.join(parts)}")
        else:
            self.lbl_features.setText("Features: None detected")

    def _export_ply(self):
        if not self.state.scan_points:
            QMessageBox.information(self, "Export", "No scan points.")
            return

        path, _ = QFileDialog.getSaveFileName(self, "Export PLY", "scan.ply",
                                               "PLY Files (*.ply)")
        if not path:
            return

        from app.export.ply_export import export_ply
        export_ply(path, np.array(self.state.scan_points))
        QMessageBox.information(self, "Export", f"PLY saved to {path}")

    def _export_csv(self):
        if not self.state.scan_points:
            QMessageBox.information(self, "Export", "No scan points.")
            return

        path, _ = QFileDialog.getSaveFileName(self, "Export CSV", "scan.csv",
                                               "CSV Files (*.csv)")
        if not path:
            return

        from app.export.csv_export import export_scan_csv
        export_scan_csv(path, self.state.scan_points)
        QMessageBox.information(self, "Export", f"CSV saved to {path}")

    def _export_stl(self):
        if self._mesh_verts is None or self._mesh_faces is None:
            QMessageBox.information(self, "Export", "Generate mesh first.")
            return

        path, _ = QFileDialog.getSaveFileName(self, "Export STL", "scan.stl",
                                               "STL Files (*.stl)")
        if not path:
            return

        from app.export.stl_export import export_stl
        export_stl(path, self._mesh_verts, self._mesh_faces)
        QMessageBox.information(self, "Export", f"STL saved to {path}")

    def _export_step(self):
        if not self._features:
            QMessageBox.information(self, "Export",
                                     "Detect features first (STEP exports parametric geometry).")
            return

        path, _ = QFileDialog.getSaveFileName(self, "Export STEP", "scan.step",
                                               "STEP Files (*.step *.stp)")
        if not path:
            return

        from app.export.step_export import export_step
        try:
            export_step(path, self._features)
            QMessageBox.information(self, "Export", f"STEP saved to {path}")
        except ImportError:
            QMessageBox.warning(self, "Export",
                                 "STEP export requires cadquery.\n"
                                 "Install with: pip install cadquery")
