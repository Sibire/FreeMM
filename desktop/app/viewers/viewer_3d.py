"""3D viewer using QOpenGLWidget for point clouds, meshes, and arm wireframe."""

import numpy as np
from PyQt5.QtWidgets import QOpenGLWidget
from PyQt5.QtCore import Qt, QPoint
from PyQt5.QtGui import QColor

try:
    from OpenGL.GL import *
    from OpenGL.GLU import *
    HAS_OPENGL = True
except ImportError:
    HAS_OPENGL = False


class Viewer3D(QOpenGLWidget):
    """Interactive 3D viewer with orbit, pan, zoom."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(400, 300)

        # Camera
        self._rot_x = 30.0
        self._rot_y = -45.0
        self._pan_x = 0.0
        self._pan_y = 0.0
        self._zoom = 400.0  # distance from target
        self._target = [0, 0, 50]  # look-at point

        # Mouse tracking
        self._last_mouse = QPoint()
        self._mouse_button = None

        # Data
        self._points = []       # list of [x,y,z]
        self._mesh_verts = None  # Nx3 vertices
        self._mesh_faces = None  # Mx3 face indices
        self._arm_joints = None  # dict with joint positions from FK
        self._features_3d = []   # detected 3D features

    def set_points(self, points):
        """Set point cloud to display."""
        self._points = list(points)
        self.update()

    def add_point(self, pt):
        """Add a single point to the cloud."""
        self._points.append(list(pt))
        self.update()

    def set_mesh(self, vertices, faces):
        """Set mesh to display."""
        self._mesh_verts = np.array(vertices, dtype=np.float32)
        self._mesh_faces = np.array(faces, dtype=np.int32)
        self.update()

    def set_arm_joints(self, joint_positions):
        """Set arm wireframe joint positions for live preview."""
        self._arm_joints = joint_positions
        self.update()

    def set_features_3d(self, features):
        """Set detected 3D features for display."""
        self._features_3d = list(features)
        self.update()

    def clear_all(self):
        self._points.clear()
        self._mesh_verts = None
        self._mesh_faces = None
        self._features_3d.clear()
        self.update()

    # --- OpenGL ---

    def initializeGL(self):
        if not HAS_OPENGL:
            return
        glClearColor(0.15, 0.15, 0.18, 1.0)
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glPointSize(3.0)
        glLineWidth(1.5)

        # Simple lighting for mesh
        glEnable(GL_LIGHTING)
        glEnable(GL_LIGHT0)
        glLightfv(GL_LIGHT0, GL_POSITION, [1, 1, 1, 0])
        glLightfv(GL_LIGHT0, GL_DIFFUSE, [0.8, 0.8, 0.8, 1])
        glLightfv(GL_LIGHT0, GL_AMBIENT, [0.3, 0.3, 0.3, 1])
        glEnable(GL_COLOR_MATERIAL)
        glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE)

    def resizeGL(self, w, h):
        if not HAS_OPENGL:
            return
        glViewport(0, 0, w, h)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        aspect = w / max(h, 1)
        gluPerspective(45, aspect, 1, 5000)
        glMatrixMode(GL_MODELVIEW)

    def paintGL(self):
        if not HAS_OPENGL:
            return
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()

        # Camera transform
        glTranslatef(-self._pan_x, -self._pan_y, -self._zoom)
        glRotatef(self._rot_x, 1, 0, 0)
        glRotatef(self._rot_y, 0, 1, 0)
        glTranslatef(-self._target[0], -self._target[1], -self._target[2])

        # Draw grid
        self._draw_grid()

        # Draw axes
        self._draw_axes()

        # Draw point cloud
        self._draw_points()

        # Draw mesh
        self._draw_mesh()

        # Draw arm wireframe
        self._draw_arm()

    def _draw_grid(self):
        glDisable(GL_LIGHTING)
        glColor4f(0.3, 0.3, 0.3, 0.5)
        glBegin(GL_LINES)
        for i in range(-20, 21):
            v = i * 10
            glVertex3f(v, 0, -200)
            glVertex3f(v, 0, 200)
            glVertex3f(-200, 0, v)
            glVertex3f(200, 0, v)
        glEnd()
        glEnable(GL_LIGHTING)

    def _draw_axes(self):
        glDisable(GL_LIGHTING)
        glLineWidth(2)
        glBegin(GL_LINES)
        # X = red
        glColor3f(1, 0.2, 0.2)
        glVertex3f(0, 0, 0)
        glVertex3f(50, 0, 0)
        # Y = green
        glColor3f(0.2, 1, 0.2)
        glVertex3f(0, 0, 0)
        glVertex3f(0, 50, 0)
        # Z = blue
        glColor3f(0.2, 0.2, 1)
        glVertex3f(0, 0, 0)
        glVertex3f(0, 0, 50)
        glEnd()
        glLineWidth(1.5)
        glEnable(GL_LIGHTING)

    def _draw_points(self):
        if not self._points:
            return
        glDisable(GL_LIGHTING)
        glColor3f(0.2, 0.8, 0.2)
        glBegin(GL_POINTS)
        for pt in self._points:
            glVertex3f(pt[0], pt[2], pt[1])  # swap Y/Z for OpenGL convention
        glEnd()
        glEnable(GL_LIGHTING)

    def _draw_mesh(self):
        if self._mesh_verts is None or self._mesh_faces is None:
            return
        glColor3f(0.4, 0.6, 0.9)
        glBegin(GL_TRIANGLES)
        for face in self._mesh_faces:
            # Compute face normal for lighting
            v0 = self._mesh_verts[face[0]]
            v1 = self._mesh_verts[face[1]]
            v2 = self._mesh_verts[face[2]]
            edge1 = v1 - v0
            edge2 = v2 - v0
            normal = np.cross(edge1, edge2)
            length = np.linalg.norm(normal)
            if length > 0:
                normal /= length
            glNormal3f(normal[0], normal[2], normal[1])
            for vi in face:
                v = self._mesh_verts[vi]
                glVertex3f(v[0], v[2], v[1])
        glEnd()

        # Wireframe overlay
        glDisable(GL_LIGHTING)
        glColor4f(0.1, 0.1, 0.1, 0.3)
        glPolygonMode(GL_FRONT_AND_BACK, GL_LINE)
        glBegin(GL_TRIANGLES)
        for face in self._mesh_faces:
            for vi in face:
                v = self._mesh_verts[vi]
                glVertex3f(v[0], v[2], v[1])
        glEnd()
        glPolygonMode(GL_FRONT_AND_BACK, GL_FILL)
        glEnable(GL_LIGHTING)

    def _draw_arm(self):
        if not self._arm_joints:
            return
        glDisable(GL_LIGHTING)
        glLineWidth(3)

        joint_order = ['base', 'shoulder', 'elbow', 'wrist', 'j5', 'tip']
        positions = []
        for name in joint_order:
            if name in self._arm_joints:
                p = self._arm_joints[name]
                if hasattr(p, '__len__'):
                    positions.append(p)

        if len(positions) < 2:
            glEnable(GL_LIGHTING)
            return

        # Draw arm links
        glColor3f(1.0, 0.7, 0.0)
        glBegin(GL_LINE_STRIP)
        for p in positions:
            glVertex3f(p[0], p[2], p[1])
        glEnd()

        # Draw joint spheres as larger points
        glPointSize(8)
        glColor3f(1.0, 0.3, 0.0)
        glBegin(GL_POINTS)
        for p in positions:
            glVertex3f(p[0], p[2], p[1])
        glEnd()

        # Tip as green dot
        tip = positions[-1]
        glPointSize(10)
        glColor3f(0.0, 1.0, 0.3)
        glBegin(GL_POINTS)
        glVertex3f(tip[0], tip[2], tip[1])
        glEnd()

        glPointSize(3)
        glLineWidth(1.5)
        glEnable(GL_LIGHTING)

    # --- Mouse interaction ---

    def mousePressEvent(self, event):
        self._last_mouse = event.pos()
        self._mouse_button = event.button()

    def mouseMoveEvent(self, event):
        dx = event.x() - self._last_mouse.x()
        dy = event.y() - self._last_mouse.y()
        self._last_mouse = event.pos()

        if self._mouse_button == Qt.LeftButton:
            self._rot_y += dx * 0.5
            self._rot_x += dy * 0.5
        elif self._mouse_button == Qt.MiddleButton:
            self._pan_x -= dx * 0.5
            self._pan_y += dy * 0.5
        elif self._mouse_button == Qt.RightButton:
            self._zoom -= dy * 2.0
            self._zoom = max(10, self._zoom)

        self.update()

    def mouseReleaseEvent(self, event):
        self._mouse_button = None

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        self._zoom -= delta * 0.3
        self._zoom = max(10, self._zoom)
        self.update()
