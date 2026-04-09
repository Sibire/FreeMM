"""Shared application state for the DIYgitizer desktop app."""

from PyQt5.QtCore import QObject, pyqtSignal
import numpy as np


class ArmState(QObject):
    """Central state container shared across all modes.

    Emits signals when state changes so UI components can react.
    """

    # Signals
    position_updated = pyqtSignal(object)       # numpy array [x,y,z]
    angles_updated = pyqtSignal(list)            # [j1,j2,j3,j4,j5] degrees
    point_added = pyqtSignal(int, object)        # (index, numpy [x,y,z])
    trace_point_added = pyqtSignal(int, float, float)  # (index, a, b)
    trace_started = pyqtSignal(str)              # plane name
    trace_stopped = pyqtSignal()
    mode_changed = pyqtSignal(str)               # mode name
    points_cleared = pyqtSignal()
    traces_cleared = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.current_angles = [0.0] * 5
        self.current_position = np.array([0.0, 0.0, 0.0])
        self.joint_positions = {}  # dict from FK: base, shoulder, etc.

        # CMM points: list of (index, np.array([x,y,z]))
        self.points = []

        # Dimensions: list of (pt_idx_a, pt_idx_b, distance)
        self.dimensions = []

        # 2D trace points: list of (index, a, b)
        self.trace_points = []
        self.trace_plane = "XZ"
        self.tracing = False

        # 3D scan points: list of np.array([x,y,z])
        self.scan_points = []
        self.scanning = False

    def update_angles(self, angles):
        """Called by connection layer when new angle data arrives."""
        self.current_angles = list(angles)
        self.angles_updated.emit(self.current_angles)

    def update_position(self, position, joint_positions=None):
        """Called by connection layer with computed tip position."""
        self.current_position = np.array(position)
        if joint_positions:
            self.joint_positions = joint_positions
        self.position_updated.emit(self.current_position)

    def add_point(self, index, x, y, z):
        """Add a sampled CMM point."""
        pt = np.array([x, y, z])
        self.points.append((index, pt))
        self.point_added.emit(index, pt)

        # If scanning in 3D mode, also accumulate
        if self.scanning:
            self.scan_points.append(pt)

    def add_trace_point(self, index, a, b):
        """Add a 2D trace point."""
        self.trace_points.append((index, a, b))
        self.trace_point_added.emit(index, a, b)

    def start_trace(self, plane):
        """Mark trace as started."""
        self.trace_plane = plane
        self.tracing = True
        self.trace_points.clear()
        self.trace_started.emit(plane)

    def stop_trace(self):
        """Mark trace as stopped."""
        self.tracing = False
        self.trace_stopped.emit()

    def add_dimension(self, idx_a, idx_b):
        """Compute and store distance between two points."""
        pt_a = None
        pt_b = None
        for idx, pt in self.points:
            if idx == idx_a:
                pt_a = pt
            if idx == idx_b:
                pt_b = pt
        if pt_a is not None and pt_b is not None:
            dist = float(np.linalg.norm(pt_a - pt_b))
            self.dimensions.append((idx_a, idx_b, dist))
            return dist
        return None

    def clear_points(self):
        """Clear all CMM points and dimensions."""
        self.points.clear()
        self.dimensions.clear()
        self.points_cleared.emit()

    def clear_traces(self):
        """Clear all trace points."""
        self.trace_points.clear()
        self.traces_cleared.emit()

    def clear_scan(self):
        """Clear 3D scan points."""
        self.scan_points.clear()

    def start_scan(self):
        """Begin 3D scanning mode."""
        self.scanning = True
        self.scan_points.clear()

    def stop_scan(self):
        """Stop 3D scanning."""
        self.scanning = False
