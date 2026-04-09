"""Simulator control panel — joint sliders and test shape selector.

Only visible when connected in simulator mode.
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider,
    QGroupBox, QComboBox, QPushButton, QDoubleSpinBox, QFrame
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont


JOINT_LIMITS = [
    ("J1 (Base Yaw)", -180, 180),
    ("J2 (Shoulder)", -105, 105),
    ("J3 (Elbow)", -145, 145),
    ("J4 (Wrist)", -180, 180),
    ("J5 (Wrist 2)", -145, 145),
]

SHAPES = [
    ("Idle (gentle oscillation)", "idle"),
    ("Manual (sliders)", "manual"),
    ("Rectangle (2D trace test)", "rectangle"),
    ("Circle (2D trace test)", "circle"),
    ("Cylinder (3D scan test)", "cylinder"),
    ("Sphere (3D scan test)", "sphere"),
]


class SimulatorPanel(QWidget):
    """Collapsible panel for controlling the simulator."""

    mode_changed = pyqtSignal(str)          # mode name
    joint_changed = pyqtSignal(int, float)  # joint index, angle in degrees
    speed_changed = pyqtSignal(float)       # speed multiplier

    def __init__(self, parent=None):
        super().__init__(parent)
        self._sliders = []
        self._value_labels = []
        self._setup_ui()
        self.setVisible(False)  # hidden until simulator connects

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 2, 6, 2)
        layout.setSpacing(4)

        # Mode selector
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("Simulator:"))
        self._mode_combo = QComboBox()
        for display_name, _ in SHAPES:
            self._mode_combo.addItem(display_name)
        self._mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        mode_layout.addWidget(self._mode_combo, stretch=1)

        self._speed_label = QLabel("Speed:")
        mode_layout.addWidget(self._speed_label)
        self._speed_spin = QDoubleSpinBox()
        self._speed_spin.setRange(0.1, 5.0)
        self._speed_spin.setValue(1.0)
        self._speed_spin.setSingleStep(0.1)
        self._speed_spin.setSuffix("x")
        self._speed_spin.valueChanged.connect(self._on_speed_changed)
        mode_layout.addWidget(self._speed_spin)

        layout.addLayout(mode_layout)

        # Joint sliders (collapsed into a group box)
        self._slider_group = QGroupBox("Joint Angles")
        slider_layout = QVBoxLayout(self._slider_group)
        slider_layout.setSpacing(2)

        for i, (name, lo, hi) in enumerate(JOINT_LIMITS):
            row = QHBoxLayout()

            lbl = QLabel(name)
            lbl.setFixedWidth(110)
            lbl.setFont(QFont("", 8))
            row.addWidget(lbl)

            slider = QSlider(Qt.Horizontal)
            slider.setRange(lo * 10, hi * 10)  # 0.1° resolution
            slider.setValue(0)
            slider.setTickPosition(QSlider.TicksBelow)
            slider.setTickInterval((hi - lo) * 10 // 10)
            row.addWidget(slider, stretch=1)

            val_label = QLabel("0.0°")
            val_label.setFixedWidth(50)
            val_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            val_label.setFont(QFont("", 8))
            row.addWidget(val_label)

            slider_layout.addLayout(row)
            self._sliders.append(slider)
            self._value_labels.append(val_label)

            # Connect slider
            idx = i  # capture loop variable
            slider.valueChanged.connect(lambda v, j=idx: self._on_slider_moved(j, v))

        # Zero all button
        zero_btn = QPushButton("Zero All")
        zero_btn.clicked.connect(self._zero_all)
        slider_layout.addWidget(zero_btn)

        layout.addWidget(self._slider_group)
        self._slider_group.setVisible(False)  # shown only in manual mode

        # Shape info label
        self._info_label = QLabel("")
        self._info_label.setWordWrap(True)
        self._info_label.setFont(QFont("", 8))
        self._info_label.setStyleSheet("color: #888;")
        layout.addWidget(self._info_label)

        self._on_mode_changed(0)

    def _on_mode_changed(self, index):
        _, mode = SHAPES[index]
        self._slider_group.setVisible(mode == 'manual')
        self._speed_label.setVisible(mode not in ('manual', 'idle'))
        self._speed_spin.setVisible(mode not in ('manual', 'idle'))

        info_map = {
            'idle': "Arm oscillates gently. Good for checking the live readout works.",
            'manual': "Drag sliders to position the arm. Press P to capture points.",
            'rectangle': "Traces a 60×40mm rectangle in the XY plane at reach ~150mm. Use 2D Trace mode to capture.",
            'circle': "Traces a R=30mm circle in the XY plane at reach ~150mm. Use 2D Trace mode to capture.",
            'cylinder': "Scans a R=25mm, H=50mm cylinder surface. Use 3D Digitizer mode.",
            'sphere': "Scans the upper hemisphere of a R=30mm sphere. Use 3D Digitizer mode.",
        }
        self._info_label.setText(info_map.get(mode, ""))
        self.mode_changed.emit(mode)

    def _on_slider_moved(self, joint_index, raw_value):
        angle = raw_value / 10.0
        self._value_labels[joint_index].setText(f"{angle:.1f}°")
        self.joint_changed.emit(joint_index, angle)

    def _on_speed_changed(self, value):
        self.speed_changed.emit(value)

    def _zero_all(self):
        for slider in self._sliders:
            slider.setValue(0)

    def get_current_mode(self):
        _, mode = SHAPES[self._mode_combo.currentIndex()]
        return mode
