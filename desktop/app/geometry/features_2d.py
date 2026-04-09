"""2D feature detection — LINE, ARC, CIRCLE fitting from trace points."""

import numpy as np
from scipy.optimize import least_squares


def fit_line(points):
    """Fit a line to 2D points. Returns dict with start, end, length, residual."""
    pts = np.array(points)
    if len(pts) < 2:
        return None

    # Direction: from first to last point
    start = pts[0]
    end = pts[-1]
    direction = end - start
    length = np.linalg.norm(direction)
    if length < 1e-6:
        return None

    direction_norm = direction / length

    # Project all points onto line and compute residuals
    vecs = pts - start
    projections = np.dot(vecs, direction_norm)
    projected = start + np.outer(projections, direction_norm)
    residuals = np.linalg.norm(pts - projected, axis=1)
    residual = float(np.mean(residuals))

    # Actual start/end from projections
    t_min = float(np.min(projections))
    t_max = float(np.max(projections))
    actual_start = start + t_min * direction_norm
    actual_end = start + t_max * direction_norm
    actual_length = t_max - t_min

    return {
        'type': 'LINE',
        'start': actual_start.tolist(),
        'end': actual_end.tolist(),
        'length': actual_length,
        'residual': residual,
    }


def fit_circle(points):
    """Fit a circle to 2D points using least-squares.

    Returns dict with center, radius, residual.
    """
    pts = np.array(points)
    if len(pts) < 3:
        return None

    # Initial guess: centroid and mean distance
    cx0 = np.mean(pts[:, 0])
    cy0 = np.mean(pts[:, 1])
    r0 = np.mean(np.sqrt((pts[:, 0] - cx0)**2 + (pts[:, 1] - cy0)**2))

    def residual_fn(params):
        cx, cy, r = params
        dists = np.sqrt((pts[:, 0] - cx)**2 + (pts[:, 1] - cy)**2)
        return dists - r

    result = least_squares(residual_fn, [cx0, cy0, r0])
    cx, cy, r = result.x
    residual = float(np.mean(np.abs(result.fun)))

    return {
        'type': 'CIRCLE',
        'center': [float(cx), float(cy)],
        'radius': float(abs(r)),
        'residual': residual,
    }


def fit_arc(points):
    """Fit a circular arc to 2D points.

    Returns dict with center, radius, start_angle, span_angle, residual.
    """
    circle = fit_circle(points)
    if circle is None:
        return None

    pts = np.array(points)
    cx, cy = circle['center']
    r = circle['radius']

    # Compute angles of each point relative to center
    angles = np.arctan2(pts[:, 1] - cy, pts[:, 0] - cx)
    angles_deg = np.degrees(angles)

    # Sort and find the arc span
    start_angle = float(angles_deg[0])
    end_angle = float(angles_deg[-1])

    # Compute span (handle wraparound)
    span = end_angle - start_angle
    if span > 180:
        span -= 360
    elif span < -180:
        span += 360

    return {
        'type': 'ARC',
        'center': circle['center'],
        'radius': r,
        'start_angle': start_angle,
        'span_angle': float(span),
        'residual': circle['residual'],
    }


def detect_features(points, line_threshold=1.0, arc_threshold=1.0):
    """Detect features in a sequence of 2D points.

    Segments the point sequence into LINE, ARC, or CIRCLE features
    using a greedy approach.

    Args:
        points: Nx2 array or list of (a, b) tuples
        line_threshold: max residual (mm) to accept a line fit
        arc_threshold: max residual (mm) to accept an arc fit

    Returns:
        list of feature dicts
    """
    pts = np.array(points)
    if len(pts) < 2:
        return []

    # Check if the trace is closed (forms a loop)
    is_closed = np.linalg.norm(pts[0] - pts[-1]) < 5.0  # within 5mm

    # Try fitting the whole thing as a circle first
    if is_closed and len(pts) >= 10:
        circle = fit_circle(pts)
        if circle and circle['residual'] < arc_threshold:
            return [circle]

    # Segment into features using a greedy sliding window
    features = []
    i = 0
    min_segment = 5  # minimum points per feature

    while i < len(pts) - 1:
        best_end = min(i + min_segment, len(pts))
        best_feature = None

        # Grow the segment as long as the fit is good
        for j in range(i + min_segment, len(pts) + 1):
            segment = pts[i:j]

            # Try line fit
            line = fit_line(segment)
            if line and line['residual'] < line_threshold:
                best_end = j
                best_feature = line
                continue

            # Try arc fit
            arc = fit_arc(segment)
            if arc and arc['residual'] < arc_threshold:
                best_end = j
                best_feature = arc
                continue

            # Fit degraded — stop growing
            break

        if best_feature:
            features.append(best_feature)
        else:
            # Fallback: fit whatever we have as a line
            segment = pts[i:min(i + min_segment, len(pts))]
            line = fit_line(segment)
            if line:
                features.append(line)
            best_end = min(i + min_segment, len(pts))

        # Advance (overlap by 1 point for continuity)
        i = max(best_end - 1, i + 1)

    return features


def generate_dimensions(features):
    """Generate dimension annotations from detected features.

    Returns list of dimension dicts for the viewer.
    """
    dims = []

    for feat in features:
        if feat['type'] == 'LINE':
            dims.append({
                'type': 'LINEAR',
                'start': feat['start'],
                'end': feat['end'],
                'value': feat['length'],
            })
        elif feat['type'] in ('ARC', 'CIRCLE'):
            dims.append({
                'type': 'RADIUS',
                'center': feat['center'],
                'radius': feat['radius'],
            })

    return dims
