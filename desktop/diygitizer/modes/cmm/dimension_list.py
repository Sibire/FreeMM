"""Dimension list widget for CMM mode."""

import math
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QLabel, QAbstractItemView
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from diygitizer.models.point import Point3D, PointRecord
from diygitizer.models.dimension import DimensionRecord


class DimensionList(QWidget):
    """Displays measured dimensions between point pairs."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._dimensions = []
        self._rounding = 0.1
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        header = QLabel("Dimensions")
        header.setFont(QFont("", 10, QFont.Bold))
        layout.addWidget(header)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["#", "Points", "Distance (mm)", ""])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table)

        # Summary
        self.summary_label = QLabel("No dimensions")
        layout.addWidget(self.summary_label)

    def set_rounding(self, precision):
        self._rounding = precision
        self._refresh_all()

    def add_dimension(self, point_a, point_b):
        """Compute distance between two points and add to list.

        Args:
            point_a: PointRecord
            point_b: PointRecord

        Returns:
            DimensionRecord
        """
        dx = point_b.point.x - point_a.point.x
        dy = point_b.point.y - point_a.point.y
        dz = point_b.point.z - point_a.point.z
        distance = math.sqrt(dx * dx + dy * dy + dz * dz)

        dim = DimensionRecord(point_a=point_a, point_b=point_b, distance=distance)
        self._dimensions.append(dim)

        row = self.table.rowCount()
        self.table.insertRow(row)
        self._set_row(row, dim, len(self._dimensions))

        self._update_summary()
        return dim

    def add_dimension_from_selection(self, selected_points):
        """Add dimensions between all pairs of selected points.

        Args:
            selected_points: list of PointRecord objects

        Returns:
            list of DimensionRecord objects
        """
        dims = []
        for i in range(len(selected_points)):
            for j in range(i + 1, len(selected_points)):
                dim = self.add_dimension(selected_points[i], selected_points[j])
                dims.append(dim)
        return dims

    def get_all_dimensions(self):
        return list(self._dimensions)

    def clear_dimensions(self):
        self._dimensions.clear()
        self.table.setRowCount(0)
        self._update_summary()

    def delete_selected(self):
        rows = sorted(set(item.row() for item in self.table.selectedItems()),
                      reverse=True)
        for row in rows:
            if row < len(self._dimensions):
                self._dimensions.pop(row)
                self.table.removeRow(row)
        self._update_summary()

    def _set_row(self, row, dim, num):
        dec = self._decimal_places()
        rounded_dist = self._rv(dim.distance)

        self.table.setItem(row, 0, QTableWidgetItem(str(num)))
        self.table.setItem(row, 1,
                           QTableWidgetItem(f"P{dim.point_a.index} → P{dim.point_b.index}"))
        self.table.setItem(row, 2,
                           QTableWidgetItem(f"{rounded_dist:.{dec}f}"))
        self.table.setItem(row, 3, QTableWidgetItem("×"))

        for col in range(4):
            item = self.table.item(row, col)
            if item:
                item.setTextAlignment(Qt.AlignCenter)

    def _refresh_all(self):
        for row, dim in enumerate(self._dimensions):
            self._set_row(row, dim, row + 1)

    def _update_summary(self):
        n = len(self._dimensions)
        if n == 0:
            self.summary_label.setText("No dimensions")
        else:
            self.summary_label.setText(f"{n} dimension{'s' if n != 1 else ''}")

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
