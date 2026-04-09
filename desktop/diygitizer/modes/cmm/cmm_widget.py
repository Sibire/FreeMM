"""CMM Mode main widget.

Displays captured points, allows measuring distances between them,
and maintains a dimension list for export.
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QSplitter, QGroupBox, QFileDialog, QMessageBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from .point_table import PointTable
from .dimension_list import DimensionList
from diygitizer.export.report_export import (
    export_dimensions_csv, export_points_csv, export_report_text
)


class CMMWidget(QWidget):
    """Main CMM mode panel.

    Left side: Point table + controls
    Right side: Dimension list + controls
    """

    def __init__(self, data_store, parent=None):
        super().__init__(parent)
        self.data_store = data_store
        self._point_index = 0
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Instruction bar
        instr = QLabel("Capture points with the probe button, then select pairs to measure distances.")
        instr.setWordWrap(True)
        layout.addWidget(instr)

        # Main split: points | dimensions
        splitter = QSplitter(Qt.Horizontal)

        # Left: Point table
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)

        left_header = QLabel("Captured Points")
        left_header.setFont(QFont("", 10, QFont.Bold))
        left_layout.addWidget(left_header)

        self.point_table = PointTable()
        left_layout.addWidget(self.point_table)

        # Point buttons
        pt_btn_layout = QHBoxLayout()

        self.capture_btn = QPushButton("Capture Point (P)")
        self.capture_btn.setMinimumHeight(35)
        self.capture_btn.clicked.connect(self._capture_point)
        pt_btn_layout.addWidget(self.capture_btn)

        self.delete_pt_btn = QPushButton("Delete Selected")
        self.delete_pt_btn.clicked.connect(self.point_table.delete_selected)
        pt_btn_layout.addWidget(self.delete_pt_btn)

        self.clear_pts_btn = QPushButton("Clear All")
        self.clear_pts_btn.clicked.connect(self._clear_points)
        pt_btn_layout.addWidget(self.clear_pts_btn)

        left_layout.addLayout(pt_btn_layout)
        splitter.addWidget(left)

        # Right: Dimension list
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)

        self.dimension_list = DimensionList()
        right_layout.addWidget(self.dimension_list)

        # Dimension buttons
        dim_btn_layout = QHBoxLayout()

        self.measure_btn = QPushButton("Measure Selected")
        self.measure_btn.setMinimumHeight(35)
        self.measure_btn.setToolTip("Select 2+ points, then click to measure distances")
        self.measure_btn.clicked.connect(self._measure_selected)
        dim_btn_layout.addWidget(self.measure_btn)

        self.delete_dim_btn = QPushButton("Delete Dim")
        self.delete_dim_btn.clicked.connect(self.dimension_list.delete_selected)
        dim_btn_layout.addWidget(self.delete_dim_btn)

        self.clear_dims_btn = QPushButton("Clear Dims")
        self.clear_dims_btn.clicked.connect(self.dimension_list.clear_dimensions)
        dim_btn_layout.addWidget(self.clear_dims_btn)

        right_layout.addLayout(dim_btn_layout)

        # Export buttons
        export_layout = QHBoxLayout()

        self.export_csv_btn = QPushButton("Export Points CSV")
        self.export_csv_btn.clicked.connect(self._export_points_csv)
        export_layout.addWidget(self.export_csv_btn)

        self.export_dims_btn = QPushButton("Export Dimensions CSV")
        self.export_dims_btn.clicked.connect(self._export_dims_csv)
        export_layout.addWidget(self.export_dims_btn)

        self.export_report_btn = QPushButton("Export Report")
        self.export_report_btn.clicked.connect(self._export_report)
        export_layout.addWidget(self.export_report_btn)

        right_layout.addLayout(export_layout)
        splitter.addWidget(right)

        splitter.setSizes([400, 400])
        layout.addWidget(splitter)

    def _connect_signals(self):
        self.data_store.point_sampled.connect(self._on_point_sampled)
        self.data_store.settings_changed.connect(self._on_settings_changed)

    def _on_point_sampled(self, point_record):
        """Handle point received from hardware/simulator."""
        self.point_table.add_point(point_record)
        self.data_store.points.append(point_record)

    def _capture_point(self):
        """Manually capture current arm position as a point."""
        state = self.data_store.arm_state
        from diygitizer.models.point import Point3D, PointRecord
        self._point_index += 1
        pt = PointRecord(
            index=self._point_index,
            point=Point3D(state.tip_x, state.tip_y, state.tip_z)
        )
        self.point_table.add_point(pt)
        self.data_store.points.append(pt)

    def _measure_selected(self):
        """Measure distance between selected point pairs."""
        selected = self.point_table.get_selected_points()
        if len(selected) < 2:
            QMessageBox.information(self, "Select Points",
                                    "Select 2 or more points to measure distances.")
            return

        dims = self.dimension_list.add_dimension_from_selection(selected)
        self.data_store.dimensions.extend(dims)

    def _clear_points(self):
        self.point_table.clear_points()
        self.data_store.points.clear()
        self._point_index = 0

    def _export_points_csv(self):
        points = self.point_table.get_all_points()
        if not points:
            QMessageBox.information(self, "No Data", "No points to export.")
            return

        filepath, _ = QFileDialog.getSaveFileName(
            self, "Export Points", "points.csv", "CSV Files (*.csv)"
        )
        if filepath:
            export_points_csv(points, filepath)

    def _export_dims_csv(self):
        dims = self.dimension_list.get_all_dimensions()
        if not dims:
            QMessageBox.information(self, "No Data", "No dimensions to export.")
            return

        filepath, _ = QFileDialog.getSaveFileName(
            self, "Export Dimensions", "dimensions.csv", "CSV Files (*.csv)"
        )
        if filepath:
            export_dimensions_csv(dims, filepath)

    def _export_report(self):
        points = self.point_table.get_all_points()
        dims = self.dimension_list.get_all_dimensions()
        if not points and not dims:
            QMessageBox.information(self, "No Data", "Nothing to export.")
            return

        filepath, _ = QFileDialog.getSaveFileName(
            self, "Export Report", "cmm_report.txt", "Text Files (*.txt)"
        )
        if filepath:
            export_report_text(points, dims, filepath)

    def _on_settings_changed(self):
        r = self.data_store.settings.rounding_precision
        self.point_table.set_rounding(r)
        self.dimension_list.set_rounding(r)
