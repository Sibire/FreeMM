"""Three-mode calibration wizard.

Tab 1 — Block:  Touch faces of a 1-2-3 block from multiple arm poses.
Tab 2 — Repeat: Touch one sharp point from many configurations.
Tab 3 — Surface: Touch a flat surface from many poses.

All three feed the same FK-based optimizer that refines 5 joint offsets
and 5 link lengths simultaneously.
"""

import os
import math
import numpy as np

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QProgressBar, QFileDialog, QMessageBox,
    QFrame, QTableWidget, QTableWidgetItem, QHeaderView,
    QTabWidget, QTextEdit,
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont, QColor

from . import calibration_solver
from .calibration_solver import CalibrationCapture, CalibrationResult
from diygitizer.config import (
    BASE_HEIGHT, UPPER_ARM, FOREARM, WRIST_LINK, PROBE_LEN,
)


FACE_INSTRUCTIONS = {
    'top':    "Touch 5+ points on the TOP face (largest face, facing up).",
    'bottom': "Touch 5+ points on the BOTTOM face (flip or reach under).",
    'front':  "Touch 5+ points on the FRONT face (long side, facing you).",
    'back':   "Touch 5+ points on the BACK face (long side, away from you).",
    'left':   "Touch 5+ points on the LEFT face (short side).",
    'right':  "Touch 5+ points on the RIGHT face (short side).",
}
FACE_ORDER = calibration_solver.FACE_ORDER
MIN_POINTS_PER_FACE = 3


class CalibrationWizard(QWidget):
    """Tabbed calibration wizard with three modes."""

    calibration_complete = pyqtSignal(object)  # CalibrationResult

    def __init__(self, data_store, parent=None):
        super().__init__(parent)
        self.data_store = data_store
        self._all_captures = []       # combined across all modes
        self.calibration_result = None
        self._setup_ui()

    # ── UI setup ──────────────────────────────────────────────────────

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        title = QLabel("Calibration")
        title.setFont(QFont("", 14, QFont.Bold))
        layout.addWidget(title)

        tip = QLabel(
            "Capture data from any combination of modes below, then "
            "click Run Calibration. The optimizer adjusts 5 joint offsets "
            "and 5 link lengths to minimize total error."
        )
        tip.setWordWrap(True)
        tip.setStyleSheet("color: #aaa;")
        layout.addWidget(tip)

        # Mode tabs
        self._tabs = QTabWidget()
        self._block_tab = self._build_block_tab()
        self._repeat_tab = self._build_repeat_tab()
        self._surface_tab = self._build_surface_tab()
        self._tabs.addTab(self._block_tab, "1-2-3 Block")
        self._tabs.addTab(self._repeat_tab, "Repeatability")
        self._tabs.addTab(self._surface_tab, "Surface")
        layout.addWidget(self._tabs)

        layout.addWidget(self._separator())

        # Capture summary
        self._summary_label = QLabel("Captures: 0 total")
        self._summary_label.setFont(QFont("", 10))
        layout.addWidget(self._summary_label)

        # Results
        results_group = QGroupBox("Results")
        rl = QVBoxLayout(results_group)

        self._results_table = QTableWidget()
        self._results_table.setColumnCount(4)
        self._results_table.setHorizontalHeaderLabels(
            ["Metric", "Expected", "Measured", "Error"]
        )
        self._results_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )
        self._results_table.setMaximumHeight(160)
        rl.addWidget(self._results_table)

        self._results_text = QTextEdit()
        self._results_text.setReadOnly(True)
        self._results_text.setMaximumHeight(120)
        self._results_text.setFont(QFont("Consolas", 9))
        rl.addWidget(self._results_text)

        layout.addWidget(results_group)

        # Bottom buttons
        bl = QHBoxLayout()

        self._run_btn = QPushButton("Run Calibration")
        self._run_btn.setMinimumHeight(36)
        self._run_btn.clicked.connect(self._run_calibration)
        self._run_btn.setEnabled(False)
        bl.addWidget(self._run_btn)

        self._save_btn = QPushButton("Save")
        self._save_btn.clicked.connect(self._save)
        self._save_btn.setEnabled(False)
        bl.addWidget(self._save_btn)

        self._load_btn = QPushButton("Load")
        self._load_btn.clicked.connect(self._load)
        bl.addWidget(self._load_btn)

        self._clear_btn = QPushButton("Clear All")
        self._clear_btn.clicked.connect(self._clear_all)
        bl.addWidget(self._clear_btn)

        layout.addLayout(bl)
        layout.addStretch()

    # ── Block tab ─────────────────────────────────────────────────────

    def _build_block_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)

        desc = QLabel(
            "Place a 1-2-3 block on a flat surface. Touch each face with "
            "the probe from varied arm poses (reach in from different angles). "
            "5+ points per face, more is better."
        )
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # Face selector
        self._block_face_idx = 0
        self._block_face_points = {f: [] for f in FACE_ORDER}

        self._face_label = QLabel()
        self._face_label.setFont(QFont("", 11, QFont.Bold))
        self._face_label.setWordWrap(True)
        layout.addWidget(self._face_label)

        # Progress
        pl = QHBoxLayout()
        self._block_progress = QProgressBar()
        self._block_progress.setMaximum(len(FACE_ORDER))
        pl.addWidget(QLabel("Faces:"))
        pl.addWidget(self._block_progress)
        layout.addLayout(pl)

        self._block_count_label = QLabel("Points: 0")
        layout.addWidget(self._block_count_label)

        # Buttons
        bl = QHBoxLayout()
        self._block_capture_btn = QPushButton("Capture Point")
        self._block_capture_btn.setMinimumHeight(36)
        self._block_capture_btn.clicked.connect(self._block_capture)
        bl.addWidget(self._block_capture_btn)

        self._block_undo_btn = QPushButton("Undo Last")
        self._block_undo_btn.clicked.connect(self._block_undo)
        bl.addWidget(self._block_undo_btn)

        self._block_next_btn = QPushButton("Next Face")
        self._block_next_btn.clicked.connect(self._block_next_face)
        self._block_next_btn.setEnabled(False)
        bl.addWidget(self._block_next_btn)

        self._block_skip_btn = QPushButton("Skip")
        self._block_skip_btn.clicked.connect(self._block_next_face)
        bl.addWidget(self._block_skip_btn)

        layout.addLayout(bl)
        layout.addStretch()
        self._update_block_display()
        return w

    def _update_block_display(self):
        if self._block_face_idx < len(FACE_ORDER):
            face = FACE_ORDER[self._block_face_idx]
            self._face_label.setText(
                f"Step {self._block_face_idx + 1}/{len(FACE_ORDER)}: "
                f"{FACE_INSTRUCTIONS[face]}"
            )
            count = len(self._block_face_points[face])
            self._block_count_label.setText(
                f"Points on {face}: {count}"
            )
            self._block_next_btn.setEnabled(count >= MIN_POINTS_PER_FACE)
        else:
            self._face_label.setText("All faces done.")
            self._block_count_label.setText("")
            self._block_capture_btn.setEnabled(False)

        done = sum(1 for pts in self._block_face_points.values()
                   if len(pts) >= MIN_POINTS_PER_FACE)
        self._block_progress.setValue(done)
        self._update_summary()

    def _block_capture(self):
        if self._block_face_idx >= len(FACE_ORDER):
            return
        state = self.data_store.arm_state
        if state is None:
            return
        face = FACE_ORDER[self._block_face_idx]
        angles = np.array([state.j1, state.j2, state.j3, state.j4, state.j5])
        cap = CalibrationCapture(angles_rad=angles, label=face, group='block')
        self._block_face_points[face].append(cap)
        self._all_captures.append(cap)
        self._update_block_display()

    def _block_undo(self):
        if self._block_face_idx >= len(FACE_ORDER):
            return
        face = FACE_ORDER[self._block_face_idx]
        if self._block_face_points[face]:
            removed = self._block_face_points[face].pop()
            if removed in self._all_captures:
                self._all_captures.remove(removed)
        self._update_block_display()

    def _block_next_face(self):
        self._block_face_idx += 1
        self._update_block_display()

    # ── Repeat tab ────────────────────────────────────────────────────

    def _build_repeat_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)

        desc = QLabel(
            "Touch ONE sharp, fixed point (like a corner of the 1-2-3 block) "
            "from as many different arm configurations as possible. Reach in "
            "from the left, right, above, below, extended, tucked. 15-20 "
            "touches minimum. The optimizer will find offsets that collapse "
            "all readings to a single point."
        )
        desc.setWordWrap(True)
        layout.addWidget(desc)

        self._repeat_captures = []

        self._repeat_count_label = QLabel("Captures: 0")
        self._repeat_count_label.setFont(QFont("", 11, QFont.Bold))
        layout.addWidget(self._repeat_count_label)

        self._repeat_spread_label = QLabel("Spread: --")
        layout.addWidget(self._repeat_spread_label)

        bl = QHBoxLayout()
        self._repeat_capture_btn = QPushButton("Capture Point")
        self._repeat_capture_btn.setMinimumHeight(36)
        self._repeat_capture_btn.clicked.connect(self._repeat_capture)
        bl.addWidget(self._repeat_capture_btn)

        self._repeat_undo_btn = QPushButton("Undo Last")
        self._repeat_undo_btn.clicked.connect(self._repeat_undo)
        bl.addWidget(self._repeat_undo_btn)

        self._repeat_clear_btn = QPushButton("Clear")
        self._repeat_clear_btn.clicked.connect(self._repeat_clear)
        bl.addWidget(self._repeat_clear_btn)

        layout.addLayout(bl)
        layout.addStretch()
        return w

    def _repeat_capture(self):
        state = self.data_store.arm_state
        if state is None:
            return
        angles = np.array([state.j1, state.j2, state.j3, state.j4, state.j5])
        cap = CalibrationCapture(angles_rad=angles, label='point', group='repeat')
        self._repeat_captures.append(cap)
        self._all_captures.append(cap)
        self._update_repeat_display()

    def _repeat_undo(self):
        if self._repeat_captures:
            removed = self._repeat_captures.pop()
            if removed in self._all_captures:
                self._all_captures.remove(removed)
        self._update_repeat_display()

    def _repeat_clear(self):
        for cap in self._repeat_captures:
            if cap in self._all_captures:
                self._all_captures.remove(cap)
        self._repeat_captures.clear()
        self._update_repeat_display()

    def _update_repeat_display(self):
        n = len(self._repeat_captures)
        self._repeat_count_label.setText(f"Captures: {n}")

        if n >= 2:
            # Show current uncalibrated spread
            pts = []
            for cap in self._repeat_captures:
                from diygitizer.models.arm_state import ArmState
                s = ArmState(j1=cap.angles_rad[0], j2=cap.angles_rad[1],
                             j3=cap.angles_rad[2], j4=cap.angles_rad[3],
                             j5=cap.angles_rad[4])
                s.compute_fk()
                pts.append([s.tip_x, s.tip_y, s.tip_z])
            pts = np.array(pts)
            centroid = np.mean(pts, axis=0)
            dists = np.linalg.norm(pts - centroid, axis=1)
            self._repeat_spread_label.setText(
                f"Current spread (uncalibrated): max {dists.max():.2f}mm, "
                f"mean {dists.mean():.2f}mm"
            )
        else:
            self._repeat_spread_label.setText("Spread: --")

        self._update_summary()

    # ── Surface tab ───────────────────────────────────────────────────

    def _build_surface_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)

        desc = QLabel(
            "Touch a known flat surface (table, granite plate, glass) from "
            "many different arm configurations. 15-20+ touches, spread across "
            "the reachable area. The optimizer will adjust parameters to "
            "flatten the residuals. No known dimension needed."
        )
        desc.setWordWrap(True)
        layout.addWidget(desc)

        self._surface_captures = []

        self._surface_count_label = QLabel("Captures: 0")
        self._surface_count_label.setFont(QFont("", 11, QFont.Bold))
        layout.addWidget(self._surface_count_label)

        self._surface_flatness_label = QLabel("Flatness: --")
        layout.addWidget(self._surface_flatness_label)

        bl = QHBoxLayout()
        self._surface_capture_btn = QPushButton("Capture Point")
        self._surface_capture_btn.setMinimumHeight(36)
        self._surface_capture_btn.clicked.connect(self._surface_capture)
        bl.addWidget(self._surface_capture_btn)

        self._surface_undo_btn = QPushButton("Undo Last")
        self._surface_undo_btn.clicked.connect(self._surface_undo)
        bl.addWidget(self._surface_undo_btn)

        self._surface_clear_btn = QPushButton("Clear")
        self._surface_clear_btn.clicked.connect(self._surface_clear)
        bl.addWidget(self._surface_clear_btn)

        layout.addLayout(bl)
        layout.addStretch()
        return w

    def _surface_capture(self):
        state = self.data_store.arm_state
        if state is None:
            return
        angles = np.array([state.j1, state.j2, state.j3, state.j4, state.j5])
        cap = CalibrationCapture(angles_rad=angles, label='surface', group='surface')
        self._surface_captures.append(cap)
        self._all_captures.append(cap)
        self._update_surface_display()

    def _surface_undo(self):
        if self._surface_captures:
            removed = self._surface_captures.pop()
            if removed in self._all_captures:
                self._all_captures.remove(removed)
        self._update_surface_display()

    def _surface_clear(self):
        for cap in self._surface_captures:
            if cap in self._all_captures:
                self._all_captures.remove(cap)
        self._surface_captures.clear()
        self._update_surface_display()

    def _update_surface_display(self):
        n = len(self._surface_captures)
        self._surface_count_label.setText(f"Captures: {n}")

        if n >= 3:
            pts = []
            for cap in self._surface_captures:
                from diygitizer.models.arm_state import ArmState
                s = ArmState(j1=cap.angles_rad[0], j2=cap.angles_rad[1],
                             j3=cap.angles_rad[2], j4=cap.angles_rad[3],
                             j5=cap.angles_rad[4])
                s.compute_fk()
                pts.append([s.tip_x, s.tip_y, s.tip_z])
            pts = np.array(pts)
            normal, d, _ = calibration_solver.fit_plane(pts)
            distances = np.abs(pts @ normal - d)
            self._surface_flatness_label.setText(
                f"Current flatness (uncalibrated): max {distances.max():.2f}mm, "
                f"mean {distances.mean():.2f}mm"
            )
        else:
            self._surface_flatness_label.setText("Flatness: --")

        self._update_summary()

    # ── Shared ────────────────────────────────────────────────────────

    def _update_summary(self):
        block_n = sum(len(pts) for pts in self._block_face_points.values())
        repeat_n = len(self._repeat_captures)
        surface_n = len(self._surface_captures)
        total = block_n + repeat_n + surface_n
        parts = []
        if block_n:
            parts.append(f"{block_n} block")
        if repeat_n:
            parts.append(f"{repeat_n} repeat")
        if surface_n:
            parts.append(f"{surface_n} surface")
        detail = ", ".join(parts) if parts else "none"
        self._summary_label.setText(f"Captures: {total} total ({detail})")
        self._run_btn.setEnabled(total >= 6)

    def _run_calibration(self):
        if len(self._all_captures) < 6:
            QMessageBox.warning(
                self, "Insufficient Data",
                "Need at least 6 captures across any combination of modes."
            )
            return

        try:
            self.calibration_result = calibration_solver.optimize(
                self._all_captures
            )
        except Exception as e:
            QMessageBox.critical(
                self, "Calibration Failed", f"Optimizer error:\n{e}"
            )
            return

        self._display_results()
        self._save_btn.setEnabled(True)
        self.calibration_complete.emit(self.calibration_result)

    def _display_results(self):
        cal = self.calibration_result
        if not cal:
            return

        # Table: face pair errors (if block data)
        rows = []
        for pair_name, data in cal.face_errors.items():
            rows.append((pair_name,
                         f"{data['expected']:.1f}",
                         f"{data['measured']:.3f}",
                         f"{data['error']:.3f}",
                         abs(data['error'])))

        if cal.repeatability_mm > 0:
            rows.append(("Repeatability", "--",
                         f"{cal.repeatability_mm:.3f}", "--", 0))
        if cal.flatness_mm > 0:
            rows.append(("Surface flatness", "--",
                         f"{cal.flatness_mm:.3f}", "--", 0))

        self._results_table.setRowCount(len(rows))
        for i, (name, exp, meas, err, err_abs) in enumerate(rows):
            self._results_table.setItem(i, 0, QTableWidgetItem(name))
            self._results_table.setItem(i, 1, QTableWidgetItem(exp))
            self._results_table.setItem(i, 2, QTableWidgetItem(meas))
            item = QTableWidgetItem(err)
            if err != "--" and err_abs > 2.0:
                item.setForeground(QColor(255, 80, 80))
            elif err != "--" and err_abs > 1.0:
                item.setForeground(QColor(255, 200, 50))
            else:
                item.setForeground(QColor(80, 255, 80))
            self._results_table.setItem(i, 3, item)

        # Text summary
        lines = []
        lines.append(f"Optimizer iterations: {cal.iterations}")
        lines.append(f"Residual error:  {cal.residual_error_mm:.3f} mm")
        if cal.repeatability_mm > 0:
            lines.append(f"Repeatability:   {cal.repeatability_mm:.3f} mm (max spread)")
        if cal.flatness_mm > 0:
            lines.append(f"Flatness:        {cal.flatness_mm:.3f} mm (max deviation)")
        lines.append("")
        lines.append("Joint offsets:")
        joint_names = ["J1 (base)", "J2 (shoulder)", "J3 (elbow)",
                       "J4 (wrist)", "J5 (wrist 2)"]
        for name, off in zip(joint_names, cal.joint_offsets_deg):
            lines.append(f"  {name:16s} {off:+.4f} deg")
        lines.append("")
        lines.append("Link lengths (calibrated vs nominal):")
        ll = cal.link_lengths
        nominal = {
            'base_height': BASE_HEIGHT, 'upper_arm': UPPER_ARM,
            'forearm': FOREARM, 'wrist_link': WRIST_LINK, 'probe_len': PROBE_LEN,
        }
        for key, val in ll.items():
            nom = nominal.get(key, 0)
            diff = val - nom
            lines.append(f"  {key:14s} {val:8.2f} mm  ({diff:+.2f})")

        self._results_text.setPlainText("\n".join(lines))

    def _save(self):
        if not self.calibration_result:
            return
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Save Calibration", "calibration.json",
            "JSON Files (*.json)"
        )
        if filepath:
            calibration_solver.save_calibration(self.calibration_result, filepath)

    def _load(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Load Calibration", "", "JSON Files (*.json)"
        )
        if filepath and os.path.exists(filepath):
            self.calibration_result = calibration_solver.load_calibration(filepath)
            self._display_results()
            self._save_btn.setEnabled(True)
            self.calibration_complete.emit(self.calibration_result)

    def _clear_all(self):
        self._all_captures.clear()
        self._block_face_points = {f: [] for f in FACE_ORDER}
        self._block_face_idx = 0
        self._repeat_captures.clear()
        self._surface_captures.clear()
        self.calibration_result = None
        self._results_table.setRowCount(0)
        self._results_text.clear()
        self._save_btn.setEnabled(False)
        self._block_capture_btn.setEnabled(True)
        self._update_block_display()
        self._update_repeat_display()
        self._update_surface_display()

    def _separator(self):
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        return line
