"""2D feature fitting: LINE, ARC, CIRCLE.

All geometry decomposes into simplest primitives with dimensioned offsets.
No splines — a complex curve becomes multiple arcs with dimensioned radii.
"""

import math
import numpy as np
from scipy.optimize import least_squares


def fit_line_2d(points):
    """Fit a line segment to a set of 2D points.

    Args:
        points: Nx2 numpy array

    Returns:
        dict with type="LINE", start, end, length, rms_error, angle_deg
    """
    if len(points) < 2:
        return None

    # SVD-based line fit
    centroid = np.mean(points, axis=0)
    centered = points - centroid
    _, _, Vt = np.linalg.svd(centered, full_matrices=False)
    direction = Vt[0]

    # Project all points onto the line to find endpoints
    projections = centered @ direction
    t_min = np.min(projections)
    t_max = np.max(projections)

    start = centroid + t_min * direction
    end = centroid + t_max * direction

    # Compute RMS error (distance from each point to the line)
    perp = np.array([-direction[1], direction[0]])
    distances = np.abs(centered @ perp)
    rms_error = np.sqrt(np.mean(distances ** 2))

    length = np.linalg.norm(end - start)
    angle = math.degrees(math.atan2(direction[1], direction[0]))

    return {
        'type': 'LINE',
        'start': tuple(start),
        'end': tuple(end),
        'length': length,
        'angle_deg': angle,
        'rms_error': rms_error,
    }


def fit_arc_2d(points):
    """Fit a circular arc to a set of 2D points.

    Uses Kasa circle fit (algebraic) then refines with least_squares.

    Args:
        points: Nx2 numpy array

    Returns:
        dict with type="ARC", center, radius, start_angle, end_angle, rms_error
    """
    if len(points) < 3:
        return None

    # Kasa algebraic circle fit
    cx, cy, r = _kasa_circle_fit(points)

    # Refine with geometric least squares
    def residuals(params):
        cx, cy, r = params
        distances = np.sqrt((points[:, 0] - cx)**2 + (points[:, 1] - cy)**2)
        return distances - r

    result = least_squares(residuals, [cx, cy, r])
    cx, cy, r = result.x
    r = abs(r)

    # Compute angles for each point relative to center
    angles = np.degrees(np.arctan2(points[:, 1] - cy, points[:, 0] - cx))

    # Find the arc span: walk along the point sequence
    start_angle = angles[0]
    end_angle = angles[-1]

    # Normalize to [0, 360)
    start_angle = start_angle % 360
    end_angle = end_angle % 360

    # Compute RMS error
    distances = np.sqrt((points[:, 0] - cx)**2 + (points[:, 1] - cy)**2)
    rms_error = np.sqrt(np.mean((distances - r) ** 2))

    return {
        'type': 'ARC',
        'center': (cx, cy),
        'radius': r,
        'start_angle': start_angle,
        'end_angle': end_angle,
        'rms_error': rms_error,
    }


def fit_circle_2d(points):
    """Fit a full circle to a set of 2D points.

    Args:
        points: Nx2 numpy array

    Returns:
        dict with type="CIRCLE", center, radius, rms_error
    """
    if len(points) < 3:
        return None

    cx, cy, r = _kasa_circle_fit(points)

    # Refine
    def residuals(params):
        cx, cy, r = params
        distances = np.sqrt((points[:, 0] - cx)**2 + (points[:, 1] - cy)**2)
        return distances - r

    result = least_squares(residuals, [cx, cy, r])
    cx, cy, r = result.x
    r = abs(r)

    distances = np.sqrt((points[:, 0] - cx)**2 + (points[:, 1] - cy)**2)
    rms_error = np.sqrt(np.mean((distances - r) ** 2))

    return {
        'type': 'CIRCLE',
        'center': (cx, cy),
        'radius': r,
        'rms_error': rms_error,
    }


def classify_segment(points, line_threshold=0.5):
    """Classify a segment of points as LINE or ARC.

    Fits both and returns whichever has lower error.
    Only returns ARC if it's significantly better than LINE.

    Args:
        points: Nx2 numpy array (segment between two corners)
        line_threshold: max RMS error (mm) to accept a line fit

    Returns:
        feature dict (LINE or ARC)
    """
    if len(points) < 2:
        return None

    line = fit_line_2d(points)

    if len(points) < 3:
        return line

    arc = fit_arc_2d(points)

    if line is None:
        return arc
    if arc is None:
        return line

    # Prefer LINE unless ARC is significantly better
    # (simpler is better for Fusion editability)
    if line['rms_error'] <= line_threshold:
        return line

    if arc['rms_error'] < line['rms_error'] * 0.5:
        return arc

    return line


def detect_circle(points, closure_threshold=5.0, circle_rms_threshold=1.0):
    """Check if a closed set of points forms a full circle.

    Args:
        points: Nx2 numpy array
        closure_threshold: max distance (mm) between first and last point
        circle_rms_threshold: max RMS error (mm) for circle fit

    Returns:
        CIRCLE feature dict or None
    """
    if len(points) < 8:
        return None

    # Check if trace is closed
    dist_close = np.linalg.norm(points[0] - points[-1])
    if dist_close > closure_threshold:
        return None

    circle = fit_circle_2d(points)
    if circle and circle['rms_error'] < circle_rms_threshold:
        return circle

    return None


def _kasa_circle_fit(points):
    """Kasa algebraic circle fit. Fast initial estimate.

    Solves: (x - cx)^2 + (y - cy)^2 = r^2
    Linearized: 2*cx*x + 2*cy*y + (r^2 - cx^2 - cy^2) = x^2 + y^2
    """
    x = points[:, 0]
    y = points[:, 1]
    A = np.column_stack([2 * x, 2 * y, np.ones(len(x))])
    b = x**2 + y**2
    result, _, _, _ = np.linalg.lstsq(A, b, rcond=None)
    cx, cy, c = result
    r = math.sqrt(c + cx**2 + cy**2)
    return cx, cy, r
