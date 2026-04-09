"""Live XYZ / joint-angle readout widget."""

import math

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from diygitizer.config import round_to, DEFAULT_ROUNDING
from diygitizer.models.arm_state import ArmState


class LiveReadout(QWidget):
    """Displays the current arm tip position (X, Y, Z) in large font
    and the five joint angles (J1-J5) in a smaller font below.

    Call :meth:`update_state` whenever new angle data arrives.
    Call :meth:`set_precision` to change rounding.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._precision = DEFAULT_ROUNDING
        self._connected = False
        self._build_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 4, 8, 4)

        # --- Position frame ---
        self._frame = QFrame()
        self._frame.setFrameShape(QFrame.StyledPanel)
        self._frame.setStyleSheet(self._frame_style(False))
        frame_layout = QVBoxLayout(self._frame)

        # Large XYZ readout
        pos_layout = QHBoxLayout()
        self._x_label = self._make_coord_label("X")
        self._y_label = self._make_coord_label("Y")
        self._z_label = self._make_coord_label("Z")
        for lbl in (self._x_label, self._y_label, self._z_label):
            pos_layout.addWidget(lbl)
        frame_layout.addLayout(pos_layout)

        # Smaller joint-angle readout
        angles_layout = QHBoxLayout()
        self._joint_labels = []
        for i in range(5):
            lbl = QLabel(f"J{i+1}: 0.0\u00b0")
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet("font-size: 11px; color: #888;")
            angles_layout.addWidget(lbl)
            self._joint_labels.append(lbl)
        frame_layout.addLayout(angles_layout)

        outer.addWidget(self._frame)

    @staticmethod
    def _make_coord_label(axis: str) -> QLabel:
        lbl = QLabel(f"{axis}: 0.000")
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet("font-size: 22px; font-weight: bold; font-family: monospace;")
        return lbl

    @staticmethod
    def _frame_style(connected: bool) -> str:
        border_color = "#4caf50" if connected else "#666"
        border_width = "2px" if connected else "1px"
        return (
            f"QFrame {{ border: {border_width} solid {border_color}; "
            f"border-radius: 6px; padding: 4px; }}"
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update_state(self, state: ArmState):
        """Refresh the display from an :class:`ArmState`."""
        p = self._precision
        self._x_label.setText("X: {}".format(self._fmt(round_to(state.tip_x, p))))
        self._y_label.setText("Y: {}".format(self._fmt(round_to(state.tip_y, p))))
        self._z_label.setText("Z: {}".format(self._fmt(round_to(state.tip_z, p))))

        degs = [
            math.degrees(state.j1),
            math.degrees(state.j2),
            math.degrees(state.j3),
            math.degrees(state.j4),
            math.degrees(state.j5),
        ]
        for i, d in enumerate(degs):
            self._joint_labels[i].setText(
                "J{}: {:.1f}\u00b0".format(i + 1, round_to(d, 0.1))
            )

    def set_precision(self, precision: float):
        """Change the rounding precision for the position display."""
        self._precision = precision

    def set_connected(self, connected: bool):
        """Highlight the frame when connected."""
        self._connected = connected
        self._frame.setStyleSheet(self._frame_style(connected))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _fmt(self, value: float) -> str:
        """Format a value according to the current precision."""
        if self._precision >= 1.0:
            return "{:.0f}".format(value)
        elif self._precision >= 0.1:
            return "{:.1f}".format(value)
        else:
            return "{:.2f}".format(value)
