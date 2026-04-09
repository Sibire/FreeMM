"""2D trace processing pipeline.

Pipeline: raw points -> smooth -> compensate -> simplify -> detect features -> dimensions
"""

import numpy as np
from app.geometry.compensation import compensate_trace
from app.geometry.features_2d import detect_features, generate_dimensions


def smooth_points(points, window=5):
    """Moving average smoothing on 2D points.

    Args:
        points: Nx2 numpy array
        window: smoothing window size (odd number)

    Returns:
        Nx2 numpy array of smoothed points
    """
    if len(points) < window:
        return points.copy()

    pts = np.array(points, dtype=float)
    smoothed = np.zeros_like(pts)
    half = window // 2

    for i in range(len(pts)):
        lo = max(0, i - half)
        hi = min(len(pts), i + half + 1)
        smoothed[i] = np.mean(pts[lo:hi], axis=0)

    return smoothed


def simplify_rdp(points, epsilon=0.5):
    """Ramer-Douglas-Peucker simplification for 2D points.

    Args:
        points: Nx2 numpy array
        epsilon: distance threshold in mm

    Returns:
        Mx2 numpy array (M <= N) of simplified points
    """
    if len(points) <= 2:
        return points.copy()

    pts = np.array(points, dtype=float)

    # Find the point farthest from the line between first and last
    start = pts[0]
    end = pts[-1]
    line_vec = end - start
    line_len = np.linalg.norm(line_vec)

    if line_len < 1e-10:
        # All points are at the same location
        return pts[[0, -1]]

    line_unit = line_vec / line_len
    vecs = pts - start
    projections = np.dot(vecs, line_unit)
    projected = start + np.outer(projections, line_unit)
    distances = np.linalg.norm(pts - projected, axis=1)

    max_idx = int(np.argmax(distances))
    max_dist = distances[max_idx]

    if max_dist > epsilon:
        # Recurse on both halves
        left = simplify_rdp(pts[:max_idx + 1], epsilon)
        right = simplify_rdp(pts[max_idx:], epsilon)
        return np.vstack([left[:-1], right])
    else:
        return pts[[0, -1]]


def run_pipeline(raw_points, compensate=True, ball_radius=0.5,
                 smooth_window=5, simplify_epsilon=0.5,
                 line_threshold=1.0, arc_threshold=1.0):
    """Run the full trace processing pipeline.

    Args:
        raw_points: list of (a, b) tuples or Nx2 array
        compensate: apply probe radius compensation
        ball_radius: probe ball radius (mm)
        smooth_window: smoothing window size
        simplify_epsilon: RDP simplification threshold (mm)
        line_threshold: feature detection line residual threshold
        arc_threshold: feature detection arc residual threshold

    Returns:
        dict with keys:
            'raw': original points (Nx2)
            'smoothed': after smoothing (Nx2)
            'compensated': after compensation (Nx2)
            'simplified': after RDP (Mx2)
            'features': list of detected feature dicts
            'dimensions': list of dimension annotation dicts
    """
    pts = np.array(raw_points, dtype=float)

    if len(pts) < 2:
        return {
            'raw': pts,
            'smoothed': pts,
            'compensated': pts,
            'simplified': pts,
            'features': [],
            'dimensions': [],
        }

    # Step 1: Smooth
    smoothed = smooth_points(pts, smooth_window)

    # Step 2: Compensate (offset inward by ball radius)
    if compensate and len(smoothed) >= 3:
        compensated = compensate_trace(smoothed, ball_radius)
    else:
        compensated = smoothed.copy()

    # Step 3: Simplify
    simplified = simplify_rdp(compensated, simplify_epsilon)

    # Step 4: Detect features
    features = detect_features(simplified, line_threshold, arc_threshold)

    # Step 5: Generate dimensions
    dimensions = generate_dimensions(features)

    return {
        'raw': pts,
        'smoothed': smoothed,
        'compensated': compensated,
        'simplified': simplified,
        'features': features,
        'dimensions': dimensions,
    }
