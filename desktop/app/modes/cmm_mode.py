"""CMM Mode — capture points, measure distances, manage dimensions."""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QGroupBox, QHeaderView, QFileDialog, QMessageBox,
    QSplitter
)
from PyQt5.QtCore import Qt
import numpy as np


class CMMMode(QWidget):
    def __init__(self, state):
        super().__init__()
        self.state = state
        self._selected_for_measure = []
        self._build_ui()
        self._connect_signals()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        splitter = QSplitter(Qt.Vertical)

        # --- Points Table ---
        pts_group = QGroupBox("Captured Points")
        pts_layout = QVBoxLayout(pts_group)

        self.point_table = QTableWidget(0, 4)
        self.point_table.setHorizontalHeaderLabels(["#", "X (mm)", "Y (mm)", "Z (mm)"])
        self.point_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.point_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.point_table.setSelectionMode(QTableWidget.MultiSelection)
        pts_layout.addWidget(self.point_table)

        pts_btn_row = QHBoxLayout()
        self.btn_measure = QPushButton("Measure Selected")
        self.btn_measure.setToolTip("Select exactly 2 points to measure distance")
        self.btn_measure.clicked.connect(self._measure_selected)
        self.btn_clear_pts = QPushButton("Clear Points")
        self.btn_clear_pts.clicked.connect(self._clear_points)
        pts_btn_row.addWidget(self.btn_measure)
        pts_btn_row.addWidget(self.btn_clear_pts)
        pts_btn_row.addStretch()
        pts_layout.addLayout(pts_btn_row)

        splitter.addWidget(pts_group)

        # --- Dimensions Table ---
        dim_group = QGroupBox("Dimensions")
        dim_layout = QVBoxLayout(dim_group)

        self.dim_table = QTableWidget(0, 4)
        self.dim_table.setHorizontalHeaderLabels(["Point A", "Point B", "Distance (mm)", "Label"])
        self.dim_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.dim_table.setSelectionBehavior(QTableWidget.SelectRows)
        dim_layout.addWidget(self.dim_table)

        dim_btn_row = QHBoxLayout()
        self.btn_delete_dim = QPushButton("Delete Selected")
        self.btn_delete_dim.clicked.connect(self._delete_dimension)
        self.btn_export = QPushButton("Export CSV")
        self.btn_export.clicked.connect(self._export_csv)
        self.btn_clear_dims = QPushButton("Clear All")
        self.btn_clear_dims.clicked.connect(self._clear_dimensions)
        dim_btn_row.addWidget(self.btn_delete_dim)
        dim_btn_row.addWidget(self.btn_export)
        dim_btn_row.addWidget(self.btn_clear_dims)
        dim_btn_row.addStretch()
        dim_layout.addLayout(dim_btn_row)

        splitter.addWidget(dim_group)

        # --- Live position ---
        self.lbl_live = QLabel("Tip: --- , --- , ---")
        layout.addWidget(self.lbl_live)
        layout.addWidget(splitter)

    def _connect_signals(self):
        self.state.point_added.connect(self._on_point_added)
        self.state.position_updated.connect(self._on_position_updated)
        self.state.points_cleared.connect(self._on_points_cleared)

    def _on_point_added(self, idx, pt):
        row = self.point_table.rowCount()
        self.point_table.insertRow(row)
        self.point_table.setItem(row, 0, QTableWidgetItem(str(idx)))
        self.point_table.setItem(row, 1, QTableWidgetItem(f"{pt[0]:.2f}"))
        self.point_table.setItem(row, 2, QTableWidgetItem(f"{pt[1]:.2f}"))
        self.point_table.setItem(row, 3, QTableWidgetItem(f"{pt[2]:.2f}"))
        self.point_table.scrollToBottom()

    def _on_position_updated(self, pos):
        self.lbl_live.setText(f"Tip: {pos[0]:.1f}, {pos[1]:.1f}, {pos[2]:.1f}")

    def _on_points_cleared(self):
        self.point_table.setRowCount(0)

    def _measure_selected(self):
        rows = self.point_table.selectionModel().selectedRows()
        if len(rows) != 2:
            QMessageBox.information(self, "Measure", "Select exactly 2 points to measure.")
            return

        row_a = rows[0].row()
        row_b = rows[1].row()
        idx_a = int(self.point_table.item(row_a, 0).text())
        idx_b = int(self.point_table.item(row_b, 0).text())

        dist = self.state.add_dimension(idx_a, idx_b)
        if dist is not None:
            row = self.dim_table.rowCount()
            self.dim_table.insertRow(row)
            self.dim_table.setItem(row, 0, QTableWidgetItem(f"P{idx_a}"))
            self.dim_table.setItem(row, 1, QTableWidgetItem(f"P{idx_b}"))
            self.dim_table.setItem(row, 2, QTableWidgetItem(f"{dist:.3f}"))
            # Editable label column
            label_item = QTableWidgetItem("")
            label_item.setFlags(label_item.flags() | Qt.ItemIsEditable)
            self.dim_table.setItem(row, 3, label_item)

    def _delete_dimension(self):
        rows = sorted(set(r.row() for r in self.dim_table.selectionModel().selectedRows()), reverse=True)
        for row in rows:
            if row < len(self.state.dimensions):
                self.state.dimensions.pop(row)
            self.dim_table.removeRow(row)

    def _clear_points(self):
        self.state.clear_points()

    def _clear_dimensions(self):
        self.state.dimensions.clear()
        self.dim_table.setRowCount(0)

    def _export_csv(self):
        if not self.state.dimensions:
            QMessageBox.information(self, "Export", "No dimensions to export.")
            return

        path, _ = QFileDialog.getSaveFileName(self, "Export Dimensions", "dimensions.csv",
                                               "CSV Files (*.csv)")
        if not path:
            return

        from app.export.csv_export import export_dimensions_csv
        export_dimensions_csv(path, self.state.points, self.state.dimensions, self.dim_table)
