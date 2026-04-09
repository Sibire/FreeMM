"""2D drawing canvas for trace mode.

Renders fitted features with dimension annotations using QPainter.
Supports pan and zoom.
"""

import math
import numpy as np
from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import Qt, QPointF, QRectF
from PyQt5.QtGui import (
    QPainter, QPen, QColor, QFont, QBrush, QPainterPath,
    QTransform, QWheelEvent
)


class Canvas2D(QWidget):
    """2D drawing canvas that displays trace data and fitted features."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(400, 300)
        self.setMouseTracking(True)

        # Data
        self._raw_points = np.empty((0, 2))
        self._features = []
        self._rounding = 0.1

        # View transform
        self._scale = 2.0  # pixels per mm
        self._offset_x = 0.0
        self._offset_y = 0.0
        self._dragging = False
        self._drag_start = None
        self._drag_offset_start = (0, 0)

        # Colors
        self._bg_color = QColor(32, 32, 32)
        self._grid_color = QColor(60, 60, 60)
        self._raw_color = QColor(100, 100, 100, 120)
        self._feature_color = QColor(0, 200, 255)
        self._dim_color = QColor(255, 180, 0)
        self._point_color = QColor(255, 80, 80)

    def set_raw_points(self, points):
        """Set raw trace points (Nx2 array)."""
        self._raw_points = points if len(points) > 0 else np.empty((0, 2))
        self._auto_fit()
        self.update()

    def set_features(self, features):
        """Set fitted features for display."""
        self._features = features
        self.update()

    def set_rounding(self, precision):
        self._rounding = precision
        self.update()

    def clear(self):
        self._raw_points = np.empty((0, 2))
        self._features = []
        self.update()

    # --- Coordinate transforms ---

    def _world_to_screen(self, wx, wy):
        sx = wx * self._scale + self._offset_x + self.width() / 2
        sy = -wy * self._scale + self._offset_y + self.height() / 2  # flip Y
        return sx, sy

    def _screen_to_world(self, sx, sy):
        wx = (sx - self._offset_x - self.width() / 2) / self._scale
        wy = -(sy - self._offset_y - self.height() / 2) / self._scale
        return wx, wy

    def _auto_fit(self):
        """Auto-fit view to show all data."""
        if len(self._raw_points) == 0:
            return

        min_xy = self._raw_points.min(axis=0)
        max_xy = self._raw_points.max(axis=0)
        data_w = max_xy[0] - min_xy[0]
        data_h = max_xy[1] - min_xy[1]

        if data_w < 0.1:
            data_w = 10
        if data_h < 0.1:
            data_h = 10

        margin = 1.2
        scale_x = self.width() / (data_w * margin)
        scale_y = self.height() / (data_h * margin)
        self._scale = min(scale_x, scale_y)

        center_x = (min_xy[0] + max_xy[0]) / 2
        center_y = (min_xy[1] + max_xy[1]) / 2
        self._offset_x = -center_x * self._scale
        self._offset_y = center_y * self._scale

    # --- Events ---

    def wheelEvent(self, event: QWheelEvent):
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self._scale *= factor
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MiddleButton or event.button() == Qt.RightButton:
            self._dragging = True
            self._drag_start = (event.x(), event.y())
            self._drag_offset_start = (self._offset_x, self._offset_y)

    def mouseMoveEvent(self, event):
        if self._dragging and self._drag_start:
            dx = event.x() - self._drag_start[0]
            dy = event.y() - self._drag_start[1]
            self._offset_x = self._drag_offset_start[0] + dx
            self._offset_y = self._drag_offset_start[1] + dy
            self.update()

    def mouseReleaseEvent(self, event):
        self._dragging = False

    # --- Painting ---

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Background
        painter.fillRect(self.rect(), self._bg_color)

        # Grid
        self._draw_grid(painter)

        # Origin crosshair
        self._draw_origin(painter)

        # Raw trace points
        self._draw_raw_points(painter)

        # Fitted features
        for feat in self._features:
            self._draw_feature(painter, feat)

        painter.end()

    def _draw_grid(self, painter):
        """Draw a reference grid."""
        painter.setPen(QPen(self._grid_color, 1, Qt.DotLine))

        # Determine grid spacing based on zoom
        grid_world = 10.0  # mm
        if self._scale * grid_world < 20:
            grid_world = 50.0
        if self._scale * grid_world < 20:
            grid_world = 100.0
        if self._scale * grid_world > 200:
            grid_world = 5.0
        if self._scale * grid_world > 200:
            grid_world = 1.0

        # Visible world bounds
        w0x, w0y = self._screen_to_world(0, self.height())
        w1x, w1y = self._screen_to_world(self.width(), 0)

        x = math.floor(w0x / grid_world) * grid_world
        while x <= w1x:
            sx, _ = self._world_to_screen(x, 0)
            painter.drawLine(int(sx), 0, int(sx), self.height())
            x += grid_world

        y = math.floor(w0y / grid_world) * grid_world
        while y <= w1y:
            _, sy = self._world_to_screen(0, y)
            painter.drawLine(0, int(sy), self.width(), int(sy))
            y += grid_world

    def _draw_origin(self, painter):
        painter.setPen(QPen(QColor(80, 80, 80), 1))
        ox, oy = self._world_to_screen(0, 0)
        painter.drawLine(int(ox) - 15, int(oy), int(ox) + 15, int(oy))
        painter.drawLine(int(ox), int(oy) - 15, int(ox), int(oy) + 15)

    def _draw_raw_points(self, painter):
        if len(self._raw_points) < 2:
            return

        painter.setPen(QPen(self._raw_color, 1))
        for i in range(len(self._raw_points) - 1):
            x0, y0 = self._world_to_screen(*self._raw_points[i])
            x1, y1 = self._world_to_screen(*self._raw_points[i + 1])
            painter.drawLine(int(x0), int(y0), int(x1), int(y1))

    def _draw_feature(self, painter, feat):
        ftype = feat['type']
        dec = self._decimal_places()

        if ftype == 'LINE':
            self._draw_line_feature(painter, feat, dec)
        elif ftype == 'ARC':
            self._draw_arc_feature(painter, feat, dec)
        elif ftype == 'CIRCLE':
            self._draw_circle_feature(painter, feat, dec)

    def _draw_line_feature(self, painter, feat, dec):
        sx, sy = self._world_to_screen(*feat['start'])
        ex, ey = self._world_to_screen(*feat['end'])

        # Draw line
        painter.setPen(QPen(self._feature_color, 2))
        painter.drawLine(int(sx), int(sy), int(ex), int(ey))

        # Draw endpoints
        painter.setBrush(QBrush(self._point_color))
        painter.setPen(Qt.NoPen)
        for px, py in [(sx, sy), (ex, ey)]:
            painter.drawEllipse(QPointF(px, py), 3, 3)

        # Dimension label
        length = feat.get('length', 0)
        rounded = self._rv(length)
        mid_x = (sx + ex) / 2
        mid_y = (sy + ey) / 2

        # Offset label perpendicular to line
        dx = ex - sx
        dy = ey - sy
        line_len = math.sqrt(dx * dx + dy * dy)
        if line_len > 1:
            nx = -dy / line_len * 15
            ny = dx / line_len * 15
        else:
            nx, ny = 0, -15

        painter.setPen(QPen(self._dim_color, 1))
        painter.setFont(QFont("", 9))
        painter.drawText(QPointF(mid_x + nx, mid_y + ny),
                         f"{rounded:.{dec}f}")

    def _draw_arc_feature(self, painter, feat, dec):
        cx, cy = self._world_to_screen(*feat['center'])
        r_screen = feat['radius'] * self._scale

        start_angle = feat['start_angle']
        end_angle = feat['end_angle']
        span = end_angle - start_angle
        if span < 0:
            span += 360

        # QPainter uses 1/16th degree units, starting from 3 o'clock, CCW
        rect = QRectF(cx - r_screen, cy - r_screen,
                       r_screen * 2, r_screen * 2)

        # Flip angles for screen Y
        qt_start = int(-end_angle * 16)
        qt_span = int(span * 16)

        painter.setPen(QPen(self._feature_color, 2))
        painter.setBrush(Qt.NoBrush)
        painter.drawArc(rect, qt_start, qt_span)

        # Center point
        painter.setBrush(QBrush(self._dim_color))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QPointF(cx, cy), 2, 2)

        # Radius dimension
        rounded_r = self._rv(feat['radius'])
        painter.setPen(QPen(self._dim_color, 1))
        painter.setFont(QFont("", 9))
        painter.drawText(QPointF(cx + 5, cy - 5),
                         f"R{rounded_r:.{dec}f}")

    def _draw_circle_feature(self, painter, feat, dec):
        cx, cy = self._world_to_screen(*feat['center'])
        r_screen = feat['radius'] * self._scale

        painter.setPen(QPen(self._feature_color, 2))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(QPointF(cx, cy), r_screen, r_screen)

        # Center point
        painter.setBrush(QBrush(self._dim_color))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QPointF(cx, cy), 2, 2)

        # Diameter dimension
        rounded_d = self._rv(feat['radius'] * 2)
        painter.setPen(QPen(self._dim_color, 1))
        painter.setFont(QFont("", 9))
        painter.drawText(QPointF(cx + r_screen + 5, cy),
                         f"⌀{rounded_d:.{dec}f}")

        # Dimension line through center
        painter.setPen(QPen(self._dim_color, 1, Qt.DashLine))
        painter.drawLine(int(cx - r_screen), int(cy),
                         int(cx + r_screen), int(cy))

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
