"""Main application window and central data store."""

import numpy as np

from PyQt5.QtCore import QObject, Qt, pyqtSignal
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import (
    QAction,
    QLabel,
    QMainWindow,
    QShortcut,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from diygitizer.models.arm_state import ArmState
from diygitizer.models.point import PointRecord
from diygitizer.models.scan import ScanSession
from diygitizer.models.settings import UserSettings

from diygitizer.connection.base import ArmConnection
from diygitizer.connection.serial_conn import SerialConnection
from diygitizer.connection.simulator import SimulatorConnection
from diygitizer.connection.reader_thread import ReaderThread

from diygitizer.widgets.connection_bar import ConnectionBar
from diygitizer.widgets.live_readout import LiveReadout
from diygitizer.widgets.settings_panel import SettingsPanel
from diygitizer.widgets.status_bar import StatusBar
from diygitizer.widgets.simulator_panel import SimulatorPanel

from diygitizer.modes.cmm.cmm_widget import CMMWidget
from diygitizer.modes.digitizer.digitizer_widget import DigitizerWidget
from diygitizer.modes.trace.trace_widget import TraceWidget
from diygitizer.calibration.calibration_wizard import CalibrationWizard


# ======================================================================
# DataStore — centralised application state
# ======================================================================


class DataStore(QObject):
    """Holds all application-level data and emits change signals.

    Every widget reads from (and writes to) the DataStore rather than
    directly communicating with each other.
    """

    arm_state_changed = pyqtSignal(object)    # ArmState
    point_sampled = pyqtSignal(object)        # PointRecord
    trace_point_added = pyqtSignal(object)    # (idx, a, b)
    connection_changed = pyqtSignal(bool)     # connected?
    settings_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.arm_state = ArmState()
        self.points: list[PointRecord] = []
        self.dimensions: list = []
        self.traces: list = []
        self.scan = ScanSession(points=np.empty((0, 3)))
        self.settings = UserSettings()

    # convenience helpers ------------------------------------------------

    def update_arm_state(self, state: ArmState):
        self.arm_state = state
        self.arm_state_changed.emit(state)

    def add_point(self, record: PointRecord):
        self.points.append(record)
        self.point_sampled.emit(record)

    def add_trace_point(self, data):
        self.traces.append(data)
        self.trace_point_added.emit(data)


# ======================================================================
# MainWindow
# ======================================================================


class MainWindow(QMainWindow):
    """Top-level application window.

    Layout (top to bottom):
        ConnectionBar
        LiveReadout
        QTabWidget  (CMM | 3D Digitizer | 2D Trace | Calibration)
        StatusBar
    """

    _SIM_TOKEN = "__simulator__"

    def __init__(self):
        super().__init__()
        self.setWindowTitle("DIYgitizer")
        self.resize(1200, 800)

        # Core objects
        self._store = DataStore(self)
        self._connection: ArmConnection | None = None
        self._reader: ReaderThread | None = None
        self._is_simulator = False

        self._build_ui()
        self._wire_signals()
        self._setup_shortcuts()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Connection bar
        self._conn_bar = ConnectionBar()
        layout.addWidget(self._conn_bar)

        # Live readout
        self._readout = LiveReadout()
        layout.addWidget(self._readout)

        # Simulator control panel (hidden until simulator connects)
        self._sim_panel = SimulatorPanel()
        layout.addWidget(self._sim_panel)

        # Tab widget for modes
        self._tabs = QTabWidget()
        self._cmm_widget = CMMWidget(self._store)
        self._digitizer_widget = DigitizerWidget(self._store)
        self._trace_widget = TraceWidget(self._store)
        self._calibration_widget = CalibrationWizard(self._store)
        self._tabs.addTab(self._cmm_widget, "CMM")
        self._tabs.addTab(self._digitizer_widget, "3D Digitizer")
        self._tabs.addTab(self._trace_widget, "2D Trace")
        self._tabs.addTab(self._calibration_widget, "Calibration")
        layout.addWidget(self._tabs, 1)  # tabs get the stretch

        # Status bar
        self._status_bar = StatusBar()
        self.setStatusBar(self._status_bar)

    @staticmethod
    def _placeholder_tab(text: str) -> QWidget:
        """Return a centred label as a placeholder for unbuilt modes."""
        w = QWidget()
        lay = QVBoxLayout(w)
        lbl = QLabel(text)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet("font-size: 18px; color: #999;")
        lay.addWidget(lbl)
        return w

    # ------------------------------------------------------------------
    # Signal wiring
    # ------------------------------------------------------------------

    def _wire_signals(self):
        # Connection bar
        self._conn_bar.connect_requested.connect(self._on_connect)
        self._conn_bar.disconnect_requested.connect(self._on_disconnect)

        # DataStore -> readout
        self._store.arm_state_changed.connect(self._readout.update_state)

        # DataStore -> status bar (connection indicator)
        self._store.connection_changed.connect(self._on_connection_changed)

        # Status bar -> settings
        self._status_bar.settings_requested.connect(self._open_settings)

        # Simulator panel -> simulator connection
        self._sim_panel.mode_changed.connect(self._on_sim_mode_changed)
        self._sim_panel.joint_changed.connect(self._on_sim_joint_changed)
        self._sim_panel.speed_changed.connect(self._on_sim_speed_changed)

    # ------------------------------------------------------------------
    # Keyboard shortcuts
    # ------------------------------------------------------------------

    def _setup_shortcuts(self):
        # 'P' key to sample a point
        sc_point = QShortcut(QKeySequence("P"), self)
        sc_point.activated.connect(self._send_sample_point)

        # 'T' key to toggle trace
        sc_trace = QShortcut(QKeySequence("T"), self)
        sc_trace.activated.connect(self._send_toggle_trace)

    def _send_sample_point(self):
        if self._connection is not None and self._connection.is_open():
            self._connection.write("p")

    def _send_toggle_trace(self):
        if self._connection is not None and self._connection.is_open():
            self._connection.write("t")

    # ------------------------------------------------------------------
    # Connect / Disconnect
    # ------------------------------------------------------------------

    def _on_connect(self, target: str):
        """Create an appropriate connection and start the reader thread."""
        # Clean up any existing connection first
        self._cleanup_connection()

        try:
            if target == self._SIM_TOKEN:
                self._connection = SimulatorConnection()
                self._is_simulator = True
            else:
                self._connection = SerialConnection(target)
                self._is_simulator = False

            self._connection.open()

            # Start reader thread
            self._reader = ReaderThread(self._connection)
            self._reader.angles_received.connect(self._store.update_arm_state)
            self._reader.point_received.connect(self._store.add_point)
            self._reader.trace_point_received.connect(self._store.add_trace_point)
            self._reader.status_received.connect(self._status_bar.set_status_message)
            self._reader.error_occurred.connect(self._on_reader_error)
            self._reader.start()

            # Store connection reference so mode widgets can send commands
            self._store._connection = self._connection

            self._store.connection_changed.emit(True)

        except Exception as exc:
            self._status_bar.set_status_message(f"Connection failed: {exc}")
            self._cleanup_connection()

    def _on_disconnect(self):
        """Stop the reader and close the connection."""
        self._cleanup_connection()
        self._store.connection_changed.emit(False)

    def _on_connection_changed(self, connected: bool):
        """Update UI widgets when connection state changes."""
        self._conn_bar.set_connected(connected)
        self._readout.set_connected(connected)
        self._status_bar.set_connected(connected, simulator=self._is_simulator)
        self._sim_panel.setVisible(connected and self._is_simulator)

    def _on_sim_mode_changed(self, mode: str):
        """Forward simulator mode change to the connection."""
        if isinstance(self._connection, SimulatorConnection):
            self._connection.set_mode(mode)

    def _on_sim_joint_changed(self, joint_index: int, angle_deg: float):
        """Forward manual joint slider change to the simulator."""
        if isinstance(self._connection, SimulatorConnection):
            self._connection.set_manual_joint(joint_index, angle_deg)

    def _on_sim_speed_changed(self, speed: float):
        """Forward speed multiplier change to the simulator."""
        if isinstance(self._connection, SimulatorConnection):
            self._connection.set_speed(speed)

    def _on_reader_error(self, msg: str):
        """Handle errors from the reader thread."""
        self._status_bar.set_status_message(f"Error: {msg}")
        self._cleanup_connection()
        self._store.connection_changed.emit(False)

    def _cleanup_connection(self):
        """Stop reader thread and close connection gracefully."""
        if self._reader is not None:
            self._reader.stop()
            self._reader.wait(2000)
            self._reader = None

        if self._connection is not None:
            try:
                self._connection.close()
            except Exception:
                pass
            self._connection = None
            self._store._connection = None

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    def _open_settings(self):
        """Open the settings dialog."""
        dlg = SettingsPanel(self._store.settings, self)
        dlg.settings_changed.connect(self._apply_settings)
        dlg.exec_()

    def _apply_settings(self, settings: UserSettings):
        """Apply updated settings from the dialog."""
        self._store.settings = settings
        self._readout.set_precision(settings.rounding_precision)
        self._store.settings_changed.emit()

    # ------------------------------------------------------------------
    # Window close
    # ------------------------------------------------------------------

    def closeEvent(self, event):
        """Clean up before closing."""
        self._cleanup_connection()
        event.accept()
