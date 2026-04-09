"""Settings dialog — rounding, ball radius, trace distance."""

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QVBoxLayout,
)

from diygitizer.config import ROUNDING_OPTIONS
from diygitizer.models.settings import UserSettings


class SettingsPanel(QDialog):
    """Modal dialog for editing :class:`UserSettings`.

    Signals
    -------
    settings_changed(UserSettings)
        Emitted when the user clicks *OK* with updated settings.
    """

    settings_changed = pyqtSignal(object)  # UserSettings

    def __init__(self, settings: UserSettings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(320)
        self._settings = settings
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        form = QFormLayout()

        # --- Rounding precision ---
        self._rounding_combo = QComboBox()
        for r in ROUNDING_OPTIONS:
            if r >= 1.0:
                self._rounding_combo.addItem("1 mm", r)
            elif r >= 0.1:
                self._rounding_combo.addItem("0.1 mm", r)
            else:
                self._rounding_combo.addItem("0.01 mm", r)
        # Select current
        for i in range(self._rounding_combo.count()):
            if self._rounding_combo.itemData(i) == self._settings.rounding_precision:
                self._rounding_combo.setCurrentIndex(i)
                break
        form.addRow("Rounding precision:", self._rounding_combo)

        # --- Ball radius ---
        self._ball_spin = QDoubleSpinBox()
        self._ball_spin.setRange(0.0, 10.0)
        self._ball_spin.setDecimals(2)
        self._ball_spin.setSingleStep(0.1)
        self._ball_spin.setSuffix(" mm")
        self._ball_spin.setValue(self._settings.ball_radius)
        form.addRow("Ball radius:", self._ball_spin)

        # --- Trace min distance ---
        self._trace_dist_spin = QDoubleSpinBox()
        self._trace_dist_spin.setRange(0.0, 50.0)
        self._trace_dist_spin.setDecimals(2)
        self._trace_dist_spin.setSingleStep(0.5)
        self._trace_dist_spin.setSuffix(" mm")
        self._trace_dist_spin.setValue(self._settings.trace_min_dist)
        form.addRow("Trace min distance:", self._trace_dist_spin)

        layout.addLayout(form)

        # --- OK / Cancel ---
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _accept(self):
        """Apply the settings and close."""
        self._settings.rounding_precision = self._rounding_combo.currentData()
        self._settings.ball_radius = self._ball_spin.value()
        self._settings.trace_min_dist = self._trace_dist_spin.value()
        self.settings_changed.emit(self._settings)
        self.accept()
