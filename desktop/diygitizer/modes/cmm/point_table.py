"""Point table widget for CMM mode."""

from PyQt5.QtWidgets import (
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView
)
from PyQt5.QtCore import Qt, pyqtSignal


class PointTable(QTableWidget):
    """Table displaying captured 3D points.

    Supports multi-selection for dimension measurement.
    """

    selection_changed = pyqtSignal(list)  # list of selected PointRecord indices

    def __init__(self, parent=None):
        super().__init__(parent)
        self._points = []
        self._rounding = 0.1

        self.setColumnCount(4)
        self.setHorizontalHeaderLabels(["#", "X (mm)", "Y (mm)", "Z (mm)"])
        self.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.verticalHeader().setVisible(False)

        self.itemSelectionChanged.connect(self._on_selection_changed)

    def set_rounding(self, precision):
        self._rounding = precision
        self._refresh_all()

    def add_point(self, point_record):
        """Add a point to the table.

        Args:
            point_record: PointRecord instance
        """
        self._points.append(point_record)
        row = self.rowCount()
        self.insertRow(row)
        self._set_row(row, point_record)
        self.scrollToBottom()

    def get_selected_points(self):
        """Get currently selected PointRecord objects."""
        selected_rows = set(item.row() for item in self.selectedItems())
        return [self._points[r] for r in sorted(selected_rows)
                if r < len(self._points)]

    def get_all_points(self):
        return list(self._points)

    def clear_points(self):
        self._points.clear()
        self.setRowCount(0)

    def delete_selected(self):
        """Delete selected points."""
        rows = sorted(set(item.row() for item in self.selectedItems()),
                      reverse=True)
        for row in rows:
            if row < len(self._points):
                self._points.pop(row)
                self.removeRow(row)

    def _set_row(self, row, pr):
        dec = self._decimal_places()
        self.setItem(row, 0, QTableWidgetItem(str(pr.index)))
        self.setItem(row, 1, QTableWidgetItem(f"{self._rv(pr.point.x):.{dec}f}"))
        self.setItem(row, 2, QTableWidgetItem(f"{self._rv(pr.point.y):.{dec}f}"))
        self.setItem(row, 3, QTableWidgetItem(f"{self._rv(pr.point.z):.{dec}f}"))

        # Center-align all cells
        for col in range(4):
            item = self.item(row, col)
            if item:
                item.setTextAlignment(Qt.AlignCenter)

    def _refresh_all(self):
        for row, pr in enumerate(self._points):
            self._set_row(row, pr)

    def _on_selection_changed(self):
        selected = self.get_selected_points()
        indices = [p.index for p in selected]
        self.selection_changed.emit(indices)

    def _rv(self, val):
        if self._rounding <= 0:
            return val
        return round(val / self._rounding) * self._rounding

    def _decimal_places(self):
        if self._rounding >= 1.0:
            return 0
        elif self._rounding >= 0.1:
            return 1
        return 2
