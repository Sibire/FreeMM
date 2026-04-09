"""Point cloud management for the 3D digitizer mode."""

import numpy as np


class PointCloudManager:
    """Manages a growing point cloud during 3D scanning.

    Handles point accumulation, minimum distance filtering,
    and probe compensation.
    """

    def __init__(self, min_distance=0.5, ball_radius=0.5):
        """
        Args:
            min_distance: minimum distance (mm) between consecutive points
            ball_radius: probe ball radius for compensation (mm)
        """
        self._points = []
        self._normals_dirty = True
        self._cached_array = None
        self.min_distance = min_distance
        self.ball_radius = ball_radius

    def add_point(self, x, y, z):
        """Add a point if it's far enough from the last point.

        Args:
            x, y, z: coordinates in mm

        Returns:
            True if point was added, False if too close to last point
        """
        pt = np.array([x, y, z])

        if self._points:
            last = self._points[-1]
            dist = np.linalg.norm(pt - last)
            if dist < self.min_distance:
                return False

        self._points.append(pt)
        self._cached_array = None
        self._normals_dirty = True
        return True

    def get_points(self):
        """Get all points as Nx3 numpy array."""
        if self._cached_array is None:
            if self._points:
                self._cached_array = np.array(self._points)
            else:
                self._cached_array = np.empty((0, 3))
        return self._cached_array

    def get_point_count(self):
        return len(self._points)

    def clear(self):
        self._points = []
        self._cached_array = None
        self._normals_dirty = True

    def get_compensated_points(self, normals=None):
        """Get points compensated for probe ball radius.

        Offsets each point along its estimated surface normal
        by -ball_radius (moving from ball center to surface contact).

        Args:
            normals: Nx3 array of pre-computed normals. If None, estimated.

        Returns:
            Nx3 numpy array of compensated points
        """
        points = self.get_points()
        if len(points) == 0 or self.ball_radius <= 0:
            return points

        if normals is None:
            from .feature_detect import estimate_normals
            normals = estimate_normals(points)

        return points - self.ball_radius * normals

    def get_bounding_box(self):
        """Get (min_xyz, max_xyz) bounding box.

        Returns:
            ((min_x, min_y, min_z), (max_x, max_y, max_z)) or None if empty
        """
        pts = self.get_points()
        if len(pts) == 0:
            return None
        return (tuple(pts.min(axis=0)), tuple(pts.max(axis=0)))

    def downsample(self, voxel_size=1.0):
        """Downsample the point cloud using voxel grid filtering.

        Args:
            voxel_size: voxel edge length in mm

        Returns:
            Nx3 numpy array of downsampled points
        """
        pts = self.get_points()
        if len(pts) == 0:
            return pts

        # Simple voxel grid: round coordinates to voxel grid, keep unique
        quantized = np.round(pts / voxel_size) * voxel_size
        _, unique_idx = np.unique(quantized, axis=0, return_index=True)
        return pts[np.sort(unique_idx)]
