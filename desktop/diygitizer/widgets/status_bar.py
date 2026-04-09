"""Custom status bar with connection indicator and settings button."""

from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtWidgets import QLabel, QPushButton, QStatusBar, QWidget, QHBoxLayout


class StatusBar(QStatusBar):
    """Application status bar.

    Shows connection status, last device message, and a gear button
    to open the settings dialog.

    Signals
    -------
    settings_requested()
        Emitted when the gear button is clicked.
    """

    settings_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        # Connection indicator
        self._conn_label = QLabel("Disconnected")
        self._conn_label.setStyleSheet("color: #f44336; font-weight: bold;")
        self.addWidget(self._conn_label)

        # Last message
        self._msg_label = QLabel("")
        self._msg_label.setStyleSheet("color: #888;")
        self.addWidget(self._msg_label, 1)  # stretch

        # Gear / settings button
        self._settings_btn = QPushButton("\u2699")  # gear unicode
        self._settings_btn.setFixedSize(28, 28)
        self._settings_btn.setToolTip("Settings")
        self._settings_btn.setStyleSheet(
            "QPushButton { font-size: 16px; border: none; }"
            "QPushButton:hover { background: #555; border-radius: 4px; }"
        )
        self._settings_btn.clicked.connect(self.settings_requested.emit)
        self.addPermanentWidget(self._settings_btn)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_connected(self, connected: bool, simulator: bool = False):
        """Update the connection indicator."""
        if connected:
            if simulator:
                self._conn_label.setText("Simulator")
                self._conn_label.setStyleSheet("color: #2196f3; font-weight: bold;")
            else:
                self._conn_label.setText("Connected")
                self._conn_label.setStyleSheet("color: #4caf50; font-weight: bold;")
        else:
            self._conn_label.setText("Disconnected")
            self._conn_label.setStyleSheet("color: #f44336; font-weight: bold;")

    def set_status_message(self, msg: str):
        """Display a status message from the device."""
        self._msg_label.setText(msg)
