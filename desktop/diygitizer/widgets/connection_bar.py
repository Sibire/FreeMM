"""Connection toolbar — port selection, connect/disconnect, simulator toggle."""

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)

from diygitizer.connection.serial_conn import list_serial_ports


class ConnectionBar(QWidget):
    """Horizontal toolbar at the top of the main window for managing
    the arm connection.

    Signals
    -------
    connect_requested(str)
        Emitted when the user clicks *Connect*.  The argument is the
        selected port name, or the literal string ``"__simulator__"``
        when the simulator checkbox is ticked.
    disconnect_requested()
        Emitted when the user clicks *Disconnect*.
    """

    connect_requested = pyqtSignal(str)
    disconnect_requested = pyqtSignal()

    _SIM_TOKEN = "__simulator__"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._connected = False
        self._build_ui()
        self._refresh_ports()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)

        # Port selector
        layout.addWidget(QLabel("Port:"))
        self._port_combo = QComboBox()
        self._port_combo.setMinimumWidth(140)
        layout.addWidget(self._port_combo)

        # Refresh button
        self._refresh_btn = QPushButton("Refresh Ports")
        self._refresh_btn.clicked.connect(self._refresh_ports)
        layout.addWidget(self._refresh_btn)

        # Simulator checkbox
        self._sim_check = QCheckBox("Simulator")
        self._sim_check.toggled.connect(self._on_sim_toggled)
        layout.addWidget(self._sim_check)

        # Connect / Disconnect button
        self._connect_btn = QPushButton("Connect")
        self._connect_btn.clicked.connect(self._on_connect_clicked)
        layout.addWidget(self._connect_btn)

        layout.addStretch()

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _refresh_ports(self):
        """Scan for available serial ports and populate the combo box."""
        self._port_combo.clear()
        ports = list_serial_ports()
        if ports:
            self._port_combo.addItems(ports)
        else:
            self._port_combo.addItem("(no ports found)")

    def _on_sim_toggled(self, checked: bool):
        """Enable/disable the port selector when simulator is toggled."""
        self._port_combo.setEnabled(not checked)
        self._refresh_btn.setEnabled(not checked)

    def _on_connect_clicked(self):
        if self._connected:
            self.disconnect_requested.emit()
        else:
            if self._sim_check.isChecked():
                self.connect_requested.emit(self._SIM_TOKEN)
            else:
                port = self._port_combo.currentText()
                if port and port != "(no ports found)":
                    self.connect_requested.emit(port)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_connected(self, connected: bool):
        """Update button text and enable-state after connect/disconnect."""
        self._connected = connected
        if connected:
            self._connect_btn.setText("Disconnect")
            self._port_combo.setEnabled(False)
            self._refresh_btn.setEnabled(False)
            self._sim_check.setEnabled(False)
        else:
            self._connect_btn.setText("Connect")
            sim = self._sim_check.isChecked()
            self._port_combo.setEnabled(not sim)
            self._refresh_btn.setEnabled(not sim)
            self._sim_check.setEnabled(True)
