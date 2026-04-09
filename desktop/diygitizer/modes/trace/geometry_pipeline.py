"""2D trace geometry pipeline.

Pipeline: raw points → smooth → probe compensate → simplify → detect corners
          → fit features (LINE/ARC/CIRCLE) → round dimensions

All geometry decomposes into simple primitives with dimensioned offsets.
"""

import math
import numpy as np
from scipy.signal import savgol_filter

from . import feature_fitting


def run_pipeline(points, ball_radius=0.5, rounding=0.1,
                 smooth_window=7, smooth_order=2,
                 simplify_epsilon=0.3, corner_angle_deg=20.0,
                 line_threshold=0.5):
    """Run the full 2D trace processing pipeline.

    Args:
        points: Nx2 numpy array of raw trace points
        ball_radius: probe ball radius for compensation (mm)
        rounding: dimension rounding precision (mm)
        smooth_window: Savitzky-Golay window size (must be odd)
        smooth_order: Savitzky-Golay polynomial order
        simplify_epsilon: RDP simplification tolerance (mm)
        corner_angle_deg: angle threshold for corner detection (degrees)
        line_threshold: max RMS error to accept a line fit (mm)

    Returns:
        dict with:
            smoothed: Nx2 smoothed points
            compensated: Nx2 compensated points
            simplified: Mx2 simplified points
            corners: list of corner indices in simplified
            features: list of feature dicts (LINE/ARC/CIRCLE)
    """
    if len(points) < 3:
        return {'smoothed': points, 'compensated': points,
                'simplified': points, 'corners': [], 'features': []}

    # Step 1: Smooth
    smoothed = smooth_trace(points, smooth_window, smooth_order)

    # Step 2: Probe radius compensation
    compensated = compensate_trace(smoothed, ball_radius)

    # Step 3: Check for full circle first
    circle = feature_fitting.detect_circle(compensated)
    if circle is not None:
        circle['radius'] = _round_val(circle['radius'], rounding)
        circle['center'] = (
            _round_val(circle['center'][0], rounding),
            _round_val(circle['center'][1], rounding),
        )
        return {
            'smoothed': smoothed,
            'compensated': compensated,
            'simplified': compensated,
            'corners': [],
            'features': [circle],
        }

    # Step 4: Simplify (Ramer-Douglas-Peucker)
    simplified = rdp_simplify(compensated, simplify_epsilon)

    # Step 5: Detect corners
    corners = detect_corners(simplified, corner_angle_deg)

    # Step 6: Fit features between corners
    features = fit_segments(compensated, simplified, corners, line_threshold)

    # Step 7: Round dimensions
    features = round_features(features, rounding)

    return {
        'smoothed': smoothed,
        'compensated': compensated,
        'simplified': simplified,
        'corners': corners,
        'features': features,
    }


def smooth_trace(points, window=7, order=2):
    """Smooth a 2D trace using Savitzky-Golay filter.

    Args:
        points: Nx2 numpy array
        window: filter window size (must be odd, >= order+2)
        order: polynomial order

    Returns:
        Nx2 numpy array of smoothed points
    """
    if len(points) < window:
        return points.copy()

    # Ensure window is odd
    if window % 2 == 0:
        window += 1

    smoothed = np.empty_like(points)
    smoothed[:, 0] = savgol_filter(points[:, 0], window, order)
    smoothed[:, 1] = savgol_filter(points[:, 1], window, order)
    return smoothed


def compensate_trace(points, ball_radius):
    """Offset trace points inward by ball radius along local normal.

    Auto-detects winding direction and offsets accordingly.

    Args:
        points: Nx2 numpy array
        ball_radius: offset distance (mm)

    Returns:
        Nx2 numpy array of compensated points
    """
    if ball_radius <= 0 or len(points) < 3:
        return points.copy()

    n = len(points)
    compensated = np.empty_like(points)

    # Estimate winding direction using signed area
    signed_area = 0.0
    for i in range(n - 1):
        signed_area += (points[i + 1, 0] - points[i, 0]) * \
                       (points[i + 1, 1] + points[i, 1])
    # positive = clockwise, negative = counterclockwise
    inward_sign = 1.0 if signed_area > 0 else -1.0

    for i in range(n):
        # Local tangent from neighbors
        if i == 0:
            tangent = points[1] - points[0]
        elif i == n - 1:
            tangent = points[n - 1] - points[n - 2]
        else:
            tangent = points[i + 1] - points[i - 1]

        tlen = np.linalg.norm(tangent)
        if tlen < 1e-10:
            compensated[i] = points[i]
            continue

        tangent = tangent / tlen
        # Normal is perpendicular to tangent (rotated 90° inward)
        normal = np.array([-tangent[1], tangent[0]]) * inward_sign

        compensated[i] = points[i] + ball_radius * normal

    return compensated


def rdp_simplify(points, epsilon):
    """Ramer-Douglas-Peucker point simplification.

    Args:
        points: Nx2 numpy array
        epsilon: tolerance distance (mm)

    Returns:
        Mx2 numpy array (M <= N) of simplified points
    """
    if len(points) <= 2:
        return points.copy()

    mask = np.zeros(len(points), dtype=bool)
    mask[0] = True
    mask[-1] = True
    _rdp_recursive(points, 0, len(points) - 1, epsilon, mask)
    return points[mask]


def _rdp_recursive(points, start, end, epsilon, mask):
    """Recursive step of RDP algorithm."""
    if end - start < 2:
        return

    # Find the point farthest from the line segment start→end
    line_vec = points[end] - points[start]
    line_len = np.linalg.norm(line_vec)

    if line_len < 1e-10:
        # Degenerate segment — keep the farthest point
        dists = np.linalg.norm(points[start + 1:end] - points[start], axis=1)
        max_idx = start + 1 + np.argmax(dists)
        if dists[max_idx - start - 1] > epsilon:
            mask[max_idx] = True
            _rdp_recursive(points, start, max_idx, epsilon, mask)
            _rdp_recursive(points, max_idx, end, epsilon, mask)
        return

    line_unit = line_vec / line_len
    perp = np.array([-line_unit[1], line_unit[0]])

    segment = points[start + 1:end]
    relative = segment - points[start]
    distances = np.abs(relative @ perp)

    max_dist_idx = np.argmax(distances)
    max_dist = distances[max_dist_idx]

    if max_dist > epsilon:
        split = start + 1 + max_dist_idx
        mask[split] = True
        _rdp_recursive(points, start, split, epsilon, mask)
        _rdp_recursive(points, split, end, epsilon, mask)


def detect_corners(points, angle_threshold_deg=20.0):
    """Detect corners where direction changes sharply.

    Args:
        points: Nx2 numpy array (simplified points)
        angle_threshold_deg: minimum angle change to count as corner

    Returns:
        list of indices in points that are corners (always includes 0 and N-1)
    """
    if len(points) <= 2:
        return list(range(len(points)))

    corners = [0]
    threshold_rad = math.radians(angle_threshold_deg)

    for i in range(1, len(points) - 1):
        v1 = points[i] - points[i - 1]
        v2 = points[i + 1] - points[i]

        len1 = np.linalg.norm(v1)
        len2 = np.linalg.norm(v2)
        if len1 < 1e-10 or len2 < 1e-10:
            continue

        cos_angle = np.clip(np.dot(v1, v2) / (len1 * len2), -1.0, 1.0)
        angle = math.acos(cos_angle)

        if angle > threshold_rad:
            corners.append(i)

    corners.append(len(points) - 1)
    return corners


def fit_segments(original_points, simplified, corner_indices, line_threshold=0.5):
    """Fit features between each pair of consecutive corners.

    Uses original (non-simplified) points for better fitting accuracy,
    but corner indices refer to simplified point positions.

    Args:
        original_points: Nx2 full point set
        simplified: Mx2 simplified points
        corner_indices: list of indices in simplified
        line_threshold: max RMS for accepting a LINE

    Returns:
        list of feature dicts
    """
    if len(corner_indices) < 2:
        return []

    features = []

    # Map simplified corner positions back to nearest original points
    corner_positions = simplified[corner_indices]
    original_indices = []
    for cp in corner_positions:
        dists = np.linalg.norm(original_points - cp, axis=1)
        original_indices.append(np.argmin(dists))

    for i in range(len(original_indices) - 1):
        idx_start = original_indices[i]
        idx_end = original_indices[i + 1]

        if idx_end <= idx_start:
            continue

        segment = original_points[idx_start:idx_end + 1]
        if len(segment) < 2:
            continue

        feat = feature_fitting.classify_segment(segment, line_threshold)
        if feat is not None:
            features.append(feat)

    return features


def round_features(features, rounding):
    """Round all dimensions in features to the specified precision.

    Args:
        features: list of feature dicts
        rounding: precision in mm (e.g., 0.1)

    Returns:
        features with rounded dimensions (modified in-place and returned)
    """
    for feat in features:
        ftype = feat['type']

        if ftype == 'LINE':
            feat['length'] = _round_val(feat['length'], rounding)
            feat['start'] = (
                _round_val(feat['start'][0], rounding),
                _round_val(feat['start'][1], rounding),
            )
            feat['end'] = (
                _round_val(feat['end'][0], rounding),
                _round_val(feat['end'][1], rounding),
            )

        elif ftype == 'ARC':
            feat['radius'] = _round_val(feat['radius'], rounding)
            feat['center'] = (
                _round_val(feat['center'][0], rounding),
                _round_val(feat['center'][1], rounding),
            )

        elif ftype == 'CIRCLE':
            feat['radius'] = _round_val(feat['radius'], rounding)
            feat['center'] = (
                _round_val(feat['center'][0], rounding),
                _round_val(feat['center'][1], rounding),
            )

    return features


def _round_val(value, rounding):
    if rounding <= 0:
        return value
    return round(value / rounding) * rounding
