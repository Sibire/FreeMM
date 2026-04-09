"""Probe radius compensation for both 2D traces and 3D surface points."""

import numpy as np


BALL_RADIUS = 0.5  # mm (1mm ruby ball)


def compensate_trace(points, ball_radius=BALL_RADIUS):
    """Offset a 2D trace inward by ball radius.

    Auto-detects trace winding direction (CW/CCW) and offsets all points
    toward the interior by the ball radius.

    Args:
        points: Nx2 numpy array of trace points (a, b)
        ball_radius: probe ball radius in mm

    Returns:
        Nx2 numpy array of compensated points
    """
    if len(points) < 3:
        return points.copy()

    pts = np.array(points, dtype=float)
    n = len(pts)

    # Compute normals at each point using neighbors
    compensated = np.zeros_like(pts)

    for i in range(n):
        prev_pt = pts[(i - 1) % n]
        next_pt = pts[(i + 1) % n]

        # Tangent direction
        tangent = next_pt - prev_pt
        length = np.linalg.norm(tangent)
        if length < 1e-10:
            compensated[i] = pts[i]
            continue
        tangent /= length

        # Inward normal (perpendicular to tangent)
        # Sign depends on winding direction
        normal = np.array([-tangent[1], tangent[0]])
        compensated[i] = pts[i] + ball_radius * normal

    # Check winding: if compensated shape is larger, we went outward — flip
    orig_area = _signed_area(pts)
    comp_area = _signed_area(compensated)

    if abs(comp_area) > abs(orig_area):
        # We expanded instead of shrinking — flip normals
        for i in range(n):
            delta = compensated[i] - pts[i]
            compensated[i] = pts[i] - delta

    return compensated


def _signed_area(pts):
    """Compute signed area of a 2D polygon (shoelace formula)."""
    n = len(pts)
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += pts[i][0] * pts[j][1]
        area -= pts[j][0] * pts[i][1]
    return area / 2.0


class ProbeCompensator3D:
    """3-point surface compensation for individual CMM points.

    Capture 3 nearby points on a surface, compute the surface normal,
    then offset subsequent points by -ball_radius along that normal
    to get the true surface contact point.
    """

    def __init__(self, ball_radius=BALL_RADIUS):
        self.ball_radius = ball_radius
        self.calibration_points = []
        self.surface_normal = None

    def add_calibration_point(self, x, y, z):
        """Add a calibration point. Need exactly 3."""
        self.calibration_points.append(np.array([x, y, z]))
        if len(self.calibration_points) == 3:
            self._compute_normal()

    def _compute_normal(self):
        """Compute surface normal from 3 calibration points."""
        p0, p1, p2 = self.calibration_points
        v1 = p1 - p0
        v2 = p2 - p0
        normal = np.cross(v1, v2)
        length = np.linalg.norm(normal)
        if length < 1e-10:
            self.surface_normal = np.array([0, 0, 1])  # fallback
        else:
            self.surface_normal = normal / length

    def is_calibrated(self):
        return self.surface_normal is not None

    def compensate_point(self, x, y, z):
        """Offset a measured point by -ball_radius along surface normal.

        Returns the estimated surface contact point.
        """
        if not self.is_calibrated():
            return np.array([x, y, z])
        pt = np.array([x, y, z])
        return pt - self.ball_radius * self.surface_normal

    def reset(self):
        """Clear calibration."""
        self.calibration_points.clear()
        self.surface_normal = None
