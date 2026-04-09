"""2D trace viewer using QGraphicsScene with pan/zoom."""

from PyQt5.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsEllipseItem
from PyQt5.QtCore import Qt, QRectF, QPointF
from PyQt5.QtGui import QPen, QBrush, QColor, QPainterPath, QFont, QTransform
import numpy as np


# Colors
COLOR_RAW = QColor(180, 180, 180)       # Raw trace points (gray)
COLOR_FITTED = QColor(50, 120, 220)      # Fitted features (blue)
COLOR_DIM = QColor(200, 60, 60)          # Dimension annotations (red)
COLOR_POINT = QColor(50, 200, 50)        # Individual points (green)
COLOR_GRID = QColor(230, 230, 230)       # Grid lines


class TraceViewer(QGraphicsView):
    """2D viewer for trace data with fitted features and dimensions."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene()
        self.setScene(self.scene)
        self.setRenderHint(self.renderHints())
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)

        # Y axis in scene: positive up (flip from screen coords)
        self.scale(1, -1)

        self._zoom = 1.0
        self._raw_points = []
        self._features = []
        self._dimensions = []

    def wheelEvent(self, event):
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self._zoom *= factor
        self.scale(factor, factor)

    def clear_all(self):
        self.scene.clear()
        self._raw_points = []
        self._features = []
        self._dimensions = []

    def set_raw_points(self, points):
        """Display raw trace points. points: list of (a, b) tuples."""
        self._raw_points = list(points)
        self._redraw()

    def set_features(self, features):
        """Display fitted features. Each feature is a dict with 'type' and geometry."""
        self._features = list(features)
        self._redraw()

    def set_dimensions(self, dimensions):
        """Display dimension annotations."""
        self._dimensions = list(dimensions)
        self._redraw()

    def _redraw(self):
        self.scene.clear()
        self._draw_grid()
        self._draw_raw_points()
        self._draw_features()
        self._draw_dimensions()

    def _draw_grid(self):
        pen = QPen(COLOR_GRID, 0.5)
        # Draw grid every 10mm, covering ±500mm
        for i in range(-50, 51):
            v = i * 10
            self.scene.addLine(v, -500, v, 500, pen)
            self.scene.addLine(-500, v, 500, v, pen)
        # Axes
        axis_pen = QPen(QColor(150, 150, 150), 1)
        self.scene.addLine(-500, 0, 500, 0, axis_pen)
        self.scene.addLine(0, -500, 0, 500, axis_pen)

    def _draw_raw_points(self):
        if not self._raw_points:
            return

        pen = QPen(COLOR_RAW, 1.5)
        r = 0.8
        for a, b in self._raw_points:
            self.scene.addEllipse(a - r, b - r, 2 * r, 2 * r, pen, QBrush(COLOR_RAW))

        # Connect with polyline
        if len(self._raw_points) > 1:
            path = QPainterPath()
            path.moveTo(self._raw_points[0][0], self._raw_points[0][1])
            for a, b in self._raw_points[1:]:
                path.lineTo(a, b)
            self.scene.addPath(path, QPen(COLOR_RAW, 0.5))

    def _draw_features(self):
        pen = QPen(COLOR_FITTED, 2)

        for feat in self._features:
            ftype = feat.get('type', '')

            if ftype == 'LINE':
                p1 = feat['start']
                p2 = feat['end']
                self.scene.addLine(p1[0], p1[1], p2[0], p2[1], pen)

            elif ftype == 'ARC':
                cx, cy = feat['center']
                r = feat['radius']
                start_deg = feat['start_angle']
                span_deg = feat['span_angle']
                rect = QRectF(cx - r, cy - r, 2 * r, 2 * r)
                # Qt uses 1/16th degree for arc angles
                self.scene.addEllipse(cx - r, cy - r, 2 * r, 2 * r,
                                       QPen(COLOR_FITTED, 0.5, Qt.DotLine))
                path = QPainterPath()
                path.arcMoveTo(rect, start_deg)
                path.arcTo(rect, start_deg, span_deg)
                self.scene.addPath(path, pen)

            elif ftype == 'CIRCLE':
                cx, cy = feat['center']
                r = feat['radius']
                self.scene.addEllipse(cx - r, cy - r, 2 * r, 2 * r, pen)

    def _draw_dimensions(self):
        pen = QPen(COLOR_DIM, 1)
        font = QFont("Arial", 8)

        for dim in self._dimensions:
            dtype = dim.get('type', '')

            if dtype == 'LINEAR':
                p1, p2 = dim['start'], dim['end']
                value = dim['value']
                # Draw dimension line
                self.scene.addLine(p1[0], p1[1], p2[0], p2[1], pen)
                # Midpoint label
                mx = (p1[0] + p2[0]) / 2
                my = (p1[1] + p2[1]) / 2
                text = self.scene.addText(f"{value:.1f}", font)
                text.setDefaultTextColor(COLOR_DIM)
                text.setPos(mx + 2, my + 2)
                # Flip text back upright (since scene is Y-flipped)
                text.setTransform(QTransform.fromScale(1, -1))

            elif dtype == 'RADIUS':
                cx, cy = dim['center']
                r = dim['radius']
                text = self.scene.addText(f"R{r:.1f}", font)
                text.setDefaultTextColor(COLOR_DIM)
                text.setPos(cx + r * 0.7, cy + r * 0.7)
                text.setTransform(QTransform.fromScale(1, -1))

    def fit_to_content(self):
        self.fitInView(self.scene.itemsBoundingRect(), Qt.KeepAspectRatio)
