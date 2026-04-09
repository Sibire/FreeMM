"""Step-by-step calibration wizard UI.

Guides user through touching faces of a 1-2-3 block to compute
correction factors for the arm.
"""

import os
import numpy as np
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QTextEdit, QProgressBar, QFileDialog, QMessageBox,
    QSpinBox, QComboBox, QFrame, QTableWidget, QTableWidgetItem,
    QHeaderView
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont

from . import calibration_solver


FACE_INSTRUCTIONS = {
    'top':    "Touch 3+ points on the TOP face (largest face, facing up)",
    'bottom': "Touch 3+ points on the BOTTOM face (flip block or reach under)",
    'front':  "Touch 3+ points on the FRONT face (long narrow face, facing you)",
    'back':   "Touch 3+ points on the BACK face (long narrow face, facing away)",
    'left':   "Touch 3+ points on the LEFT face (short narrow face)",
    'right':  "Touch 3+ points on the RIGHT face (short narrow face)",
}

FACE_ORDER = ['top', 'bottom', 'front', 'back', 'left', 'right']
MIN_POINTS_PER_FACE = 3


class CalibrationWizard(QWidget):
    """Step-by-step calibration using a 1-2-3 block."""

    calibration_complete = pyqtSignal(object)  # CalibrationResult

    def __init__(self, data_store, parent=None):
        super().__init__(parent)
        self.data_store = data_store
        self.face_points = {face: [] for face in FACE_ORDER}
        self.current_face_idx = 0
        self.calibration_result = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Title
        title = QLabel("Calibration Wizard")
        title.setFont(QFont("", 16, QFont.Bold))
        layout.addWidget(title)

        desc = QLabel(
            "Use a 1-2-3 block (25.4 × 50.8 × 76.2mm) to calibrate the arm.\n"
            "Place the block on a flat surface and touch each face with the probe."
        )
        desc.setWordWrap(True)
        layout.addWidget(desc)

        layout.addWidget(self._create_separator())

        # Current face instruction
        self.face_label = QLabel()
        self.face_label.setFont(QFont("", 12, QFont.Bold))
        self.face_label.setWordWrap(True)
        layout.addWidget(self.face_label)

        # Progress
        progress_layout = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(len(FACE_ORDER))
        self.progress_bar.setValue(0)
        progress_layout.addWidget(QLabel("Faces completed:"))
        progress_layout.addWidget(self.progress_bar)
        layout.addLayout(progress_layout)

        # Point count for current face
        self.point_count_label = QLabel("Points captured: 0")
        self.point_count_label.setFont(QFont("", 11))
        layout.addWidget(self.point_count_label)

        # Buttons
        btn_layout = QHBoxLayout()

        self.capture_btn = QPushButton("Capture Point")
        self.capture_btn.setMinimumHeight(40)
        self.capture_btn.clicked.connect(self._capture_point)
        btn_layout.addWidget(self.capture_btn)

        self.next_face_btn = QPushButton("Next Face →")
        self.next_face_btn.setMinimumHeight(40)
        self.next_face_btn.clicked.connect(self._next_face)
        self.next_face_btn.setEnabled(False)
        btn_layout.addWidget(self.next_face_btn)

        self.skip_btn = QPushButton("Skip Face")
        self.skip_btn.clicked.connect(self._skip_face)
        btn_layout.addWidget(self.skip_btn)

        layout.addLayout(btn_layout)

        layout.addWidget(self._create_separator())

        # Results area
        results_group = QGroupBox("Calibration Results")
        results_layout = QVBoxLayout(results_group)

        self.results_table = QTableWidget()
        self.results_table.setColumnCount(4)
        self.results_table.setHorizontalHeaderLabels([
            "Face Pair", "Expected (mm)", "Measured (mm)", "Error (mm)"
        ])
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.results_table.setMaximumHeight(120)
        results_layout.addWidget(self.results_table)

        self.residual_label = QLabel("Residual error: --")
        self.residual_label.setFont(QFont("", 11, QFont.Bold))
        results_layout.addWidget(self.residual_label)

        layout.addWidget(results_group)

        # Bottom buttons
        bottom_layout = QHBoxLayout()

        self.run_cal_btn = QPushButton("Run Calibration")
        self.run_cal_btn.setMinimumHeight(35)
        self.run_cal_btn.clicked.connect(self._run_calibration)
        self.run_cal_btn.setEnabled(False)
        bottom_layout.addWidget(self.run_cal_btn)

        self.save_btn = QPushButton("Save Calibration")
        self.save_btn.setMinimumHeight(35)
        self.save_btn.clicked.connect(self._save_calibration)
        self.save_btn.setEnabled(False)
        bottom_layout.addWidget(self.save_btn)

        self.load_btn = QPushButton("Load Calibration")
        self.load_btn.setMinimumHeight(35)
        self.load_btn.clicked.connect(self._load_calibration)
        bottom_layout.addWidget(self.load_btn)

        self.reset_btn = QPushButton("Reset")
        self.reset_btn.clicked.connect(self._reset)
        bottom_layout.addWidget(self.reset_btn)

        layout.addLayout(bottom_layout)
        layout.addStretch()

        self._update_display()

    def _create_separator(self):
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        return line

    def _update_display(self):
        if self.current_face_idx < len(FACE_ORDER):
            face = FACE_ORDER[self.current_face_idx]
            self.face_label.setText(
                f"Step {self.current_face_idx + 1}/{len(FACE_ORDER)}: "
                f"{FACE_INSTRUCTIONS[face]}"
            )
            count = len(self.face_points[face])
            self.point_count_label.setText(f"Points captured for {face}: {count}")
            self.next_face_btn.setEnabled(count >= MIN_POINTS_PER_FACE)
            self.capture_btn.setEnabled(True)
        else:
            self.face_label.setText("All faces captured. Ready to calibrate.")
            self.point_count_label.setText("")
            self.capture_btn.setEnabled(False)
            self.next_face_btn.setEnabled(False)

        # Enable calibration if we have at least 3 faces with enough points
        faces_done = sum(1 for pts in self.face_points.values()
                         if len(pts) >= MIN_POINTS_PER_FACE)
        self.run_cal_btn.setEnabled(faces_done >= 3)
        self.progress_bar.setValue(faces_done)

    def _capture_point(self):
        if self.current_face_idx >= len(FACE_ORDER):
            return

        state = self.data_store.arm_state
        pt = np.array([state.tip_x, state.tip_y, state.tip_z])
        face = FACE_ORDER[self.current_face_idx]
        self.face_points[face].append(pt)
        self._update_display()

    def _next_face(self):
        self.current_face_idx += 1
        self._update_display()

    def _skip_face(self):
        self.current_face_idx += 1
        self._update_display()

    def _run_calibration(self):
        # Convert lists to numpy arrays
        face_arrays = {}
        for face, pts in self.face_points.items():
            if len(pts) >= MIN_POINTS_PER_FACE:
                face_arrays[face] = np.array(pts)

        if len(face_arrays) < 3:
            QMessageBox.warning(self, "Insufficient Data",
                                "Need at least 3 faces with 3+ points each.")
            return

        current_lengths = {
            'base_height': 50.0,
            'upper_arm': 150.0,
            'forearm': 130.0,
            'wrist_link': 30.0,
            'probe_len': 20.0,
        }

        self.calibration_result = calibration_solver.calibrate_from_block(
            face_arrays, current_link_lengths=current_lengths
        )

        self._display_results()
        self.save_btn.setEnabled(True)
        self.calibration_complete.emit(self.calibration_result)

    def _display_results(self):
        if not self.calibration_result:
            return

        errors = self.calibration_result.face_errors
        self.results_table.setRowCount(len(errors))

        for row, (pair_name, data) in enumerate(errors.items()):
            self.results_table.setItem(row, 0, QTableWidgetItem(pair_name))
            self.results_table.setItem(row, 1,
                                       QTableWidgetItem(f"{data['expected']:.1f}"))
            self.results_table.setItem(row, 2,
                                       QTableWidgetItem(f"{data['measured']:.3f}"))

            error_item = QTableWidgetItem(f"{data['error']:.3f}")
            if abs(data['error']) > 2.0:
                error_item.setForeground(Qt.red)
            elif abs(data['error']) > 1.0:
                error_item.setForeground(Qt.darkYellow)
            self.results_table.setItem(row, 3, error_item)

        self.residual_label.setText(
            f"Residual error: {self.calibration_result.residual_error_mm:.3f} mm"
        )
        scale = self.calibration_result.scale_factors
        self.residual_label.setText(
            self.residual_label.text() +
            f"  |  Scale: X={scale[0]:.4f} Y={scale[1]:.4f} Z={scale[2]:.4f}"
        )

    def _save_calibration(self):
        if not self.calibration_result:
            return

        filepath, _ = QFileDialog.getSaveFileName(
            self, "Save Calibration", "calibration_data.json",
            "JSON Files (*.json)"
        )
        if filepath:
            calibration_solver.save_calibration(self.calibration_result, filepath)
            QMessageBox.information(self, "Saved",
                                    f"Calibration saved to {filepath}")

    def _load_calibration(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Load Calibration", "",
            "JSON Files (*.json)"
        )
        if filepath and os.path.exists(filepath):
            self.calibration_result = calibration_solver.load_calibration(filepath)
            self._display_results()
            self.save_btn.setEnabled(True)
            self.calibration_complete.emit(self.calibration_result)
            QMessageBox.information(self, "Loaded",
                                    f"Calibration loaded from {filepath}")

    def _reset(self):
        self.face_points = {face: [] for face in FACE_ORDER}
        self.current_face_idx = 0
        self.calibration_result = None
        self.results_table.setRowCount(0)
        self.residual_label.setText("Residual error: --")
        self.save_btn.setEnabled(False)
        self._update_display()
