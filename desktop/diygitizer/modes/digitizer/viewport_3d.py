"""3D viewport for digitizer mode using QOpenGLWidget.

Renders point clouds, meshes, arm skeleton, and fitted feature overlays
with dimension labels. Supports arcball camera (orbit, pan, zoom).
"""

import math
import numpy as np

from PyQt5.QtWidgets import QOpenGLWidget
from PyQt5.QtCore import Qt, QPointF
from PyQt5.QtGui import QFont, QPainter, QColor

try:
    from OpenGL.GL import *
    from OpenGL.GLU import *
    HAS_OPENGL = True
except ImportError:
    HAS_OPENGL = False


class Viewport3D(QOpenGLWidget):
    """OpenGL-based 3D viewport with arcball camera."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(400, 300)

        # Camera (spherical coordinates)
        self._cam_theta = 45.0    # horizontal angle (degrees)
        self._cam_phi = 30.0      # vertical angle (degrees)
        self._cam_dist = 400.0    # distance from look-at point
        self._look_at = [0.0, 0.0, 50.0]  # look-at point

        # Mouse interaction
        self._last_mouse = None
        self._mouse_button = None

        # Data
        self._point_cloud = np.empty((0, 3))
        self._mesh_verts = None
        self._mesh_faces = None
        self._arm_joints = None  # list of (x,y,z) tuples
        self._features = []
        self._rounding = 0.1

        # Display options
        self.show_grid = True
        self.show_arm = True
        self.show_points = True
        self.show_mesh = True
        self.show_features = True
        self.point_size = 3.0

    def set_point_cloud(self, points):
        """Update point cloud data (Nx3 array)."""
        self._point_cloud = points if len(points) > 0 else np.empty((0, 3))
        self.update()

    def set_mesh(self, vertices, faces):
        """Update mesh data."""
        self._mesh_verts = vertices
        self._mesh_faces = faces
        self.update()

    def set_arm_joints(self, joints):
        """Update arm skeleton (list of (x,y,z) positions)."""
        self._arm_joints = joints
        self.update()

    def set_features(self, features):
        """Update detected features for overlay rendering."""
        self._features = features
        self.update()

    def set_rounding(self, precision):
        self._rounding = precision
        self.update()

    def clear_all(self):
        self._point_cloud = np.empty((0, 3))
        self._mesh_verts = None
        self._mesh_faces = None
        self._features = []
        self.update()

    # --- OpenGL ---

    def initializeGL(self):
        if not HAS_OPENGL:
            return

        glClearColor(0.12, 0.12, 0.12, 1.0)
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glEnable(GL_POINT_SMOOTH)
        glEnable(GL_LINE_SMOOTH)

    def resizeGL(self, w, h):
        if not HAS_OPENGL:
            return
        glViewport(0, 0, w, h)

    def paintGL(self):
        if not HAS_OPENGL:
            return

        # QPainter owns the widget surface.  OpenGL calls go between
        # beginNativePainting / endNativePainting; 2D text overlay
        # uses the painter directly afterward.
        painter = QPainter(self)
        painter.beginNativePainting()

        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        self._setup_projection()
        self._setup_camera()

        if self.show_grid:
            self._draw_grid()

        if self.show_arm and self._arm_joints:
            self._draw_arm()

        if self.show_points and len(self._point_cloud) > 0:
            self._draw_point_cloud()

        if self.show_mesh and self._mesh_verts is not None:
            self._draw_mesh()

        if self.show_features and self._features:
            self._draw_features()

        painter.endNativePainting()

        # 2D text overlay (labels) drawn with QPainter after OpenGL
        self._draw_labels_with_painter(painter)
        painter.end()

    def _setup_projection(self):
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        aspect = self.width() / max(self.height(), 1)
        gluPerspective(45.0, aspect, 1.0, 5000.0)

    def _setup_camera(self):
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()

        # Compute camera position from spherical coords
        theta = math.radians(self._cam_theta)
        phi = math.radians(self._cam_phi)

        cx = self._look_at[0] + self._cam_dist * math.cos(phi) * math.cos(theta)
        cy = self._look_at[1] + self._cam_dist * math.cos(phi) * math.sin(theta)
        cz = self._look_at[2] + self._cam_dist * math.sin(phi)

        gluLookAt(cx, cy, cz,
                  self._look_at[0], self._look_at[1], self._look_at[2],
                  0, 0, 1)

    def _draw_grid(self):
        glBegin(GL_LINES)
        glColor4f(0.3, 0.3, 0.3, 0.5)
        size = 200
        step = 20
        for i in range(-size, size + 1, step):
            glVertex3f(i, -size, 0)
            glVertex3f(i, size, 0)
            glVertex3f(-size, i, 0)
            glVertex3f(size, i, 0)
        glEnd()

        # Axes
        glLineWidth(2)
        glBegin(GL_LINES)
        # X = red
        glColor3f(0.8, 0.2, 0.2)
        glVertex3f(0, 0, 0)
        glVertex3f(50, 0, 0)
        # Y = green
        glColor3f(0.2, 0.8, 0.2)
        glVertex3f(0, 0, 0)
        glVertex3f(0, 50, 0)
        # Z = blue
        glColor3f(0.2, 0.2, 0.8)
        glVertex3f(0, 0, 0)
        glVertex3f(0, 0, 50)
        glEnd()
        glLineWidth(1)

    def _draw_arm(self):
        joints = self._arm_joints
        if not joints or len(joints) < 2:
            return

        # Draw arm links as thick lines
        glLineWidth(3)
        glBegin(GL_LINE_STRIP)
        glColor3f(0.0, 0.8, 1.0)
        for jx, jy, jz in joints:
            glVertex3f(jx, jy, jz)
        glEnd()
        glLineWidth(1)

        # Draw joint spheres (as points)
        glPointSize(8)
        glBegin(GL_POINTS)
        glColor3f(1.0, 0.5, 0.0)
        for jx, jy, jz in joints:
            glVertex3f(jx, jy, jz)
        glEnd()

        # Probe tip
        tx, ty, tz = joints[-1]
        glPointSize(10)
        glBegin(GL_POINTS)
        glColor3f(1.0, 0.0, 0.0)
        glVertex3f(tx, ty, tz)
        glEnd()

    def _draw_point_cloud(self):
        glPointSize(self.point_size)
        glBegin(GL_POINTS)

        n = len(self._point_cloud)
        z_col = self._point_cloud[:, 2]
        z_min = z_col.min()
        z_range = max(z_col.max() - z_min, 1)
        for i in range(n):
            x, y, z = self._point_cloud[i]
            # Color by height
            t = (z - z_min) / z_range
            glColor3f(0.2 + 0.8 * t, 0.5, 1.0 - 0.8 * t)
            glVertex3f(x, y, z)

        glEnd()

    def _draw_mesh(self):
        if self._mesh_verts is None or self._mesh_faces is None:
            return

        # Solid faces with transparency
        glEnable(GL_LIGHTING)
        glEnable(GL_LIGHT0)
        glLightfv(GL_LIGHT0, GL_POSITION, [1, 1, 1, 0])
        glLightfv(GL_LIGHT0, GL_DIFFUSE, [0.8, 0.8, 0.8, 1])
        glMaterialfv(GL_FRONT_AND_BACK, GL_DIFFUSE, [0.3, 0.6, 0.9, 0.7])
        glMaterialfv(GL_FRONT_AND_BACK, GL_AMBIENT, [0.1, 0.2, 0.3, 0.7])

        glBegin(GL_TRIANGLES)
        for face in self._mesh_faces:
            v0 = self._mesh_verts[int(face[0])]
            v1 = self._mesh_verts[int(face[1])]
            v2 = self._mesh_verts[int(face[2])]

            # Compute normal
            edge1 = v1 - v0
            edge2 = v2 - v0
            normal = np.cross(edge1, edge2)
            norm_len = np.linalg.norm(normal)
            if norm_len > 0:
                normal = normal / norm_len
            glNormal3f(*normal)

            glVertex3f(*v0)
            glVertex3f(*v1)
            glVertex3f(*v2)
        glEnd()

        glDisable(GL_LIGHTING)

        # Wireframe overlay
        glPolygonMode(GL_FRONT_AND_BACK, GL_LINE)
        glColor4f(0.5, 0.7, 1.0, 0.3)
        glBegin(GL_TRIANGLES)
        for face in self._mesh_faces:
            for idx in face:
                glVertex3f(*self._mesh_verts[int(idx)])
        glEnd()
        glPolygonMode(GL_FRONT_AND_BACK, GL_FILL)

    def _draw_features(self):
        """Draw wireframe overlays for detected features."""
        for feat in self._features:
            ftype = feat.get('type', '')

            if ftype == 'PLANE':
                self._draw_plane_feature(feat)
            elif ftype == 'SPHERE':
                self._draw_sphere_feature(feat)
            elif ftype == 'CYLINDER':
                self._draw_cylinder_feature(feat)

    def _draw_plane_feature(self, feat):
        """Draw a plane as a transparent quad."""
        point = np.array(feat['point'])
        normal = np.array(feat['normal'])
        w, h = feat.get('bounds', (50, 50))

        # Build local coordinate frame
        if abs(normal[2]) < 0.9:
            up = np.array([0, 0, 1])
        else:
            up = np.array([1, 0, 0])
        u = np.cross(normal, up)
        u = u / np.linalg.norm(u)
        v = np.cross(normal, u)

        corners = [
            point - u * w / 2 - v * h / 2,
            point + u * w / 2 - v * h / 2,
            point + u * w / 2 + v * h / 2,
            point - u * w / 2 + v * h / 2,
        ]

        glColor4f(0.0, 1.0, 0.5, 0.2)
        glBegin(GL_QUADS)
        for c in corners:
            glVertex3f(*c)
        glEnd()

        glColor4f(0.0, 1.0, 0.5, 0.8)
        glLineWidth(2)
        glBegin(GL_LINE_LOOP)
        for c in corners:
            glVertex3f(*c)
        glEnd()
        glLineWidth(1)

    def _draw_sphere_feature(self, feat):
        """Draw sphere as wireframe circles."""
        cx, cy, cz = feat['center']
        r = feat['radius']

        glColor4f(1.0, 0.5, 0.0, 0.7)
        glLineWidth(2)

        # Draw circles in 3 planes
        segments = 36
        for plane_func in [
            lambda t: (cx + r * math.cos(t), cy + r * math.sin(t), cz),
            lambda t: (cx + r * math.cos(t), cy, cz + r * math.sin(t)),
            lambda t: (cx, cy + r * math.cos(t), cz + r * math.sin(t)),
        ]:
            glBegin(GL_LINE_LOOP)
            for i in range(segments):
                theta = 2 * math.pi * i / segments
                px, py, pz = plane_func(theta)
                glVertex3f(px, py, pz)
            glEnd()

        glLineWidth(1)

    def _draw_cylinder_feature(self, feat):
        """Draw cylinder as wireframe."""
        center = np.array(feat['center'])
        axis = np.array(feat['axis'])
        r = feat['radius']
        h = feat['height']

        # Build local frame
        if abs(axis[2]) < 0.9:
            up = np.array([0, 0, 1])
        else:
            up = np.array([1, 0, 0])
        u = np.cross(axis, up)
        u = u / max(np.linalg.norm(u), 1e-10)
        v = np.cross(axis, u)

        bottom = center - axis * h / 2
        top = center + axis * h / 2

        glColor4f(1.0, 0.8, 0.0, 0.7)
        glLineWidth(2)

        segments = 24
        # Bottom circle
        glBegin(GL_LINE_LOOP)
        for i in range(segments):
            theta = 2 * math.pi * i / segments
            pt = bottom + r * (math.cos(theta) * u + math.sin(theta) * v)
            glVertex3f(*pt)
        glEnd()

        # Top circle
        glBegin(GL_LINE_LOOP)
        for i in range(segments):
            theta = 2 * math.pi * i / segments
            pt = top + r * (math.cos(theta) * u + math.sin(theta) * v)
            glVertex3f(*pt)
        glEnd()

        # Vertical lines
        glBegin(GL_LINES)
        for i in range(0, segments, segments // 8):
            theta = 2 * math.pi * i / segments
            offset = r * (math.cos(theta) * u + math.sin(theta) * v)
            glVertex3f(*(bottom + offset))
            glVertex3f(*(top + offset))
        glEnd()

        glLineWidth(1)

    def _draw_labels_with_painter(self, painter):
        """Draw dimension labels as 2D text overlay using an active QPainter."""
        if not self._features:
            return

        painter.setRenderHint(QPainter.TextAntialiasing)
        painter.setFont(QFont("", 9))
        painter.setPen(QColor(255, 200, 50))

        dec = self._decimal_places()

        for feat in self._features:
            ftype = feat.get('type', '')
            label = ""
            world_pos = None

            if ftype == 'PLANE':
                w, h = feat.get('bounds', (0, 0))
                label = f"Plane {self._rv(w):.{dec}f}×{self._rv(h):.{dec}f}"
                world_pos = feat['point']
            elif ftype == 'SPHERE':
                label = f"⌀{self._rv(feat['radius'] * 2):.{dec}f}"
                world_pos = feat['center']
            elif ftype == 'CYLINDER':
                label = f"⌀{self._rv(feat['radius'] * 2):.{dec}f} h={self._rv(feat['height']):.{dec}f}"
                world_pos = feat['center']

            if label and world_pos:
                screen = self._project_to_screen(*world_pos)
                if screen:
                    painter.drawText(QPointF(screen[0] + 10, screen[1] - 10),
                                     label)

    def _project_to_screen(self, x, y, z):
        """Project 3D world point to 2D screen coordinates."""
        if not HAS_OPENGL:
            return None

        try:
            modelview = glGetDoublev(GL_MODELVIEW_MATRIX)
            projection = glGetDoublev(GL_PROJECTION_MATRIX)
            viewport = glGetIntegerv(GL_VIEWPORT)

            sx, sy, sz = gluProject(x, y, z, modelview, projection, viewport)

            if 0 < sz < 1:  # in front of camera
                return (sx, self.height() - sy)  # flip Y for Qt
        except Exception:
            pass
        return None

    # --- Mouse events ---

    def mousePressEvent(self, event):
        self._last_mouse = (event.x(), event.y())
        self._mouse_button = event.button()

    def mouseMoveEvent(self, event):
        if self._last_mouse is None:
            return

        dx = event.x() - self._last_mouse[0]
        dy = event.y() - self._last_mouse[1]
        self._last_mouse = (event.x(), event.y())

        if self._mouse_button == Qt.LeftButton:
            # Orbit
            self._cam_theta -= dx * 0.5
            self._cam_phi += dy * 0.5
            self._cam_phi = max(-89, min(89, self._cam_phi))
        elif self._mouse_button == Qt.RightButton:
            # Pan
            scale = self._cam_dist * 0.002
            theta = math.radians(self._cam_theta)
            self._look_at[0] += (-math.sin(theta) * dx + math.cos(theta) * dy * 0.5) * scale
            self._look_at[1] += (math.cos(theta) * dx + math.sin(theta) * dy * 0.5) * scale
            self._look_at[2] += dy * scale * 0.5

        self.update()

    def mouseReleaseEvent(self, event):
        self._last_mouse = None
        self._mouse_button = None

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if delta > 0:
            self._cam_dist *= 0.9
        else:
            self._cam_dist *= 1.1
        self._cam_dist = max(10, min(5000, self._cam_dist))
        self.update()

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
