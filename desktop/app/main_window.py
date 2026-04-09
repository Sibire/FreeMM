"""Main application window for DIYgitizer desktop app."""

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QLabel, QComboBox, QPushButton, QStatusBar, QGroupBox,
    QSlider, QGridLayout, QFrame, QSplitter
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont
import numpy as np

from app.arm_state import ArmState
from app.connection import SerialSource, SimulatorSource, list_serial_ports
from app.kinematics import JOINT_LIMITS
from app.modes.cmm_mode import CMMMode
from app.modes.trace_mode import TraceMode
from app.modes.digitizer_mode import DigitizerMode


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DIYgitizer")
        self.setMinimumSize(1200, 800)

        self.state = ArmState()
        self.source = None
        self._sim_sliders = []

        self._build_ui()
        self._connect_signals()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)

        # Left: connection panel + simulator sliders
        left_panel = self._build_left_panel()
        layout.addWidget(left_panel, stretch=0)

        # Right: mode tabs
        self.tabs = QTabWidget()
        self.cmm_mode = CMMMode(self.state)
        self.trace_mode = TraceMode(self.state)
        self.digitizer_mode = DigitizerMode(self.state)
        self.tabs.addTab(self.cmm_mode, "CMM")
        self.tabs.addTab(self.trace_mode, "2D Trace")
        self.tabs.addTab(self.digitizer_mode, "3D Digitizer")
        layout.addWidget(self.tabs, stretch=1)

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        # Live readout labels in status bar
        self.lbl_xyz = QLabel("X: --- Y: --- Z: ---")
        self.lbl_xyz.setFont(QFont("Courier", 10))
        self.lbl_angles = QLabel("J1: --- J2: --- J3: --- J4: --- J5: ---")
        self.lbl_angles.setFont(QFont("Courier", 9))
        self.lbl_conn = QLabel("Disconnected")
        self.status_bar.addWidget(self.lbl_conn)
        self.status_bar.addWidget(self._vsep())
        self.status_bar.addWidget(self.lbl_xyz, stretch=1)
        self.status_bar.addWidget(self._vsep())
        self.status_bar.addWidget(self.lbl_angles, stretch=1)

    def _vsep(self):
        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setFrameShadow(QFrame.Sunken)
        return sep

    def _build_left_panel(self):
        panel = QWidget()
        panel.setFixedWidth(260)
        layout = QVBoxLayout(panel)

        # Connection group
        conn_group = QGroupBox("Connection")
        conn_layout = QVBoxLayout(conn_group)

        # Port selector
        port_row = QHBoxLayout()
        self.port_combo = QComboBox()
        self.port_combo.addItem("Simulator")
        self.btn_refresh = QPushButton("Refresh")
        self.btn_refresh.clicked.connect(self._refresh_ports)
        port_row.addWidget(self.port_combo, stretch=1)
        port_row.addWidget(self.btn_refresh)
        conn_layout.addLayout(port_row)

        # Connect/disconnect button
        self.btn_connect = QPushButton("Connect")
        self.btn_connect.clicked.connect(self._toggle_connection)
        conn_layout.addWidget(self.btn_connect)

        layout.addWidget(conn_group)

        # Simulator joint sliders
        self.sim_group = QGroupBox("Simulator Joints")
        sim_layout = QGridLayout(self.sim_group)

        joint_names = ["J1 Yaw", "J2 Shoulder", "J3 Elbow", "J4 Wrist", "J5 Wrist2"]
        for i, name in enumerate(joint_names):
            lo, hi = JOINT_LIMITS[i]
            lbl = QLabel(name)
            slider = QSlider(Qt.Horizontal)
            slider.setMinimum(int(lo))
            slider.setMaximum(int(hi))
            slider.setValue(0)
            val_lbl = QLabel("0°")
            val_lbl.setFixedWidth(45)

            slider.valueChanged.connect(lambda v, idx=i, vl=val_lbl: self._on_sim_slider(idx, v, vl))
            sim_layout.addWidget(lbl, i, 0)
            sim_layout.addWidget(slider, i, 1)
            sim_layout.addWidget(val_lbl, i, 2)
            self._sim_sliders.append(slider)

        # Sample + Trace buttons for simulator
        btn_row = QHBoxLayout()
        self.btn_sim_sample = QPushButton("Sample (P)")
        self.btn_sim_sample.clicked.connect(lambda: self._send_cmd('p'))
        self.btn_sim_trace = QPushButton("Trace (T)")
        self.btn_sim_trace.clicked.connect(lambda: self._send_cmd('t'))
        btn_row.addWidget(self.btn_sim_sample)
        btn_row.addWidget(self.btn_sim_trace)
        sim_layout.addLayout(btn_row, len(joint_names), 0, 1, 3)

        layout.addWidget(self.sim_group)
        self.sim_group.setEnabled(False)

        layout.addStretch()
        return panel

    def _connect_signals(self):
        self.state.position_updated.connect(self._update_xyz_display)
        self.state.angles_updated.connect(self._update_angles_display)

    def _refresh_ports(self):
        current = self.port_combo.currentText()
        self.port_combo.clear()
        self.port_combo.addItem("Simulator")
        for port in list_serial_ports():
            self.port_combo.addItem(port)
        idx = self.port_combo.findText(current)
        if idx >= 0:
            self.port_combo.setCurrentIndex(idx)

    def _toggle_connection(self):
        if self.source:
            self.source.stop()
            self.source = None
            self.btn_connect.setText("Connect")
            self.lbl_conn.setText("Disconnected")
            self.sim_group.setEnabled(False)
            return

        selection = self.port_combo.currentText()
        if selection == "Simulator":
            self.source = SimulatorSource()
            self.sim_group.setEnabled(True)
        else:
            self.source = SerialSource(selection)
            self.sim_group.setEnabled(False)

        # Wire signals to state
        self.source.angles_updated.connect(self.state.update_angles)
        self.source.position_updated.connect(self.state.update_position)
        self.source.point_sampled.connect(self.state.add_point)
        self.source.trace_point.connect(self.state.add_trace_point)
        self.source.trace_started.connect(self.state.start_trace)
        self.source.trace_stopped.connect(self.state.stop_trace)
        self.source.status_message.connect(lambda m: self.status_bar.showMessage(m, 3000))
        self.source.connected.connect(lambda: self.lbl_conn.setText("Connected"))
        self.source.disconnected.connect(lambda: self.lbl_conn.setText("Disconnected"))

        self.source.start()
        self.btn_connect.setText("Disconnect")

    def _on_sim_slider(self, joint_idx, value, val_label):
        val_label.setText(f"{value}°")
        if isinstance(self.source, SimulatorSource):
            self.source.set_joint(joint_idx, value)

    def _send_cmd(self, cmd):
        if self.source:
            self.source.send_command(cmd)

    def _update_xyz_display(self, pos):
        self.lbl_xyz.setText(f"X:{pos[0]:7.1f}  Y:{pos[1]:7.1f}  Z:{pos[2]:7.1f}")

    def _update_angles_display(self, angles):
        parts = [f"J{i+1}:{a:6.1f}" for i, a in enumerate(angles)]
        self.lbl_angles.setText("  ".join(parts))

    def closeEvent(self, event):
        if self.source:
            self.source.stop()
        event.accept()
