"""3D feature detection — Plane, Cylinder, Sphere fitting via RANSAC."""

import numpy as np
from scipy.optimize import least_squares


def fit_plane(points, threshold=1.0, max_iterations=1000):
    """Fit a plane to 3D points using RANSAC.

    Args:
        points: Nx3 numpy array
        threshold: inlier distance threshold (mm)
        max_iterations: RANSAC iterations

    Returns:
        dict with normal, point, inliers, residual, or None
    """
    pts = np.array(points, dtype=float)
    n = len(pts)
    if n < 3:
        return None

    best_inliers = []
    best_normal = None
    best_d = 0

    rng = np.random.default_rng(42)

    for _ in range(max_iterations):
        # Sample 3 random points
        indices = rng.choice(n, 3, replace=False)
        p0, p1, p2 = pts[indices]

        # Compute plane normal
        v1 = p1 - p0
        v2 = p2 - p0
        normal = np.cross(v1, v2)
        norm_len = np.linalg.norm(normal)
        if norm_len < 1e-10:
            continue
        normal /= norm_len

        # Plane equation: normal . (x - p0) = 0
        d = -np.dot(normal, p0)

        # Compute distances of all points to plane
        distances = np.abs(np.dot(pts, normal) + d)
        inlier_mask = distances < threshold
        inlier_count = np.sum(inlier_mask)

        if inlier_count > len(best_inliers):
            best_inliers = np.where(inlier_mask)[0]
            best_normal = normal.copy()
            best_d = d

    if len(best_inliers) < 3:
        return None

    # Refit with all inliers
    inlier_pts = pts[best_inliers]
    centroid = np.mean(inlier_pts, axis=0)

    # SVD for best-fit plane
    centered = inlier_pts - centroid
    _, _, vh = np.linalg.svd(centered)
    refined_normal = vh[-1]

    distances = np.abs(np.dot(inlier_pts - centroid, refined_normal))
    residual = float(np.mean(distances))

    return {
        'type': 'PLANE',
        'normal': refined_normal.tolist(),
        'point': centroid.tolist(),
        'inlier_count': len(best_inliers),
        'inlier_indices': best_inliers.tolist(),
        'residual': residual,
    }


def fit_sphere(points, threshold=1.0, max_iterations=1000):
    """Fit a sphere to 3D points using RANSAC + least-squares refinement.

    Returns:
        dict with center, radius, inliers, residual, or None
    """
    pts = np.array(points, dtype=float)
    n = len(pts)
    if n < 4:
        return None

    best_inliers = []
    best_center = None
    best_radius = 0

    rng = np.random.default_rng(42)

    for _ in range(max_iterations):
        indices = rng.choice(n, 4, replace=False)
        sample = pts[indices]

        # Solve for sphere through 4 points
        center, radius = _sphere_from_4_points(sample)
        if center is None:
            continue

        distances = np.abs(np.linalg.norm(pts - center, axis=1) - radius)
        inlier_mask = distances < threshold
        inlier_count = np.sum(inlier_mask)

        if inlier_count > len(best_inliers):
            best_inliers = np.where(inlier_mask)[0]
            best_center = center
            best_radius = radius

    if len(best_inliers) < 4:
        return None

    # Refine with least squares on inliers
    inlier_pts = pts[best_inliers]
    cx, cy, cz = best_center
    r = best_radius

    def residual_fn(params):
        c = params[:3]
        r = params[3]
        return np.linalg.norm(inlier_pts - c, axis=1) - r

    result = least_squares(residual_fn, [cx, cy, cz, r])
    cx, cy, cz, r = result.x
    residual = float(np.mean(np.abs(result.fun)))

    return {
        'type': 'SPHERE',
        'center': [float(cx), float(cy), float(cz)],
        'radius': float(abs(r)),
        'inlier_count': len(best_inliers),
        'inlier_indices': best_inliers.tolist(),
        'residual': residual,
    }


def fit_cylinder(points, threshold=1.0, max_iterations=1000):
    """Fit a cylinder to 3D points using RANSAC.

    Returns:
        dict with axis_point, axis_direction, radius, inliers, residual, or None
    """
    pts = np.array(points, dtype=float)
    n = len(pts)
    if n < 6:
        return None

    best_inliers = []
    best_axis_pt = None
    best_axis_dir = None
    best_radius = 0

    rng = np.random.default_rng(42)

    for _ in range(max_iterations):
        # Sample points and estimate axis from normals
        indices = rng.choice(n, 6, replace=False)
        sample = pts[indices]

        # Estimate axis: direction of least variance
        centered = sample - np.mean(sample, axis=0)
        _, _, vh = np.linalg.svd(centered)

        # Try last singular vector as axis
        axis_dir = vh[0]  # direction of most variance — cross-section is perpendicular
        axis_pt = np.mean(sample, axis=0)

        # Project points onto plane perpendicular to axis
        projections = pts - axis_pt
        along_axis = np.dot(projections, axis_dir)[:, np.newaxis] * axis_dir
        perp = projections - along_axis
        distances_from_axis = np.linalg.norm(perp, axis=1)

        # Estimate radius as median distance
        radius = np.median(distances_from_axis)
        if radius < 1e-6:
            continue

        residuals = np.abs(distances_from_axis - radius)
        inlier_mask = residuals < threshold
        inlier_count = np.sum(inlier_mask)

        if inlier_count > len(best_inliers):
            best_inliers = np.where(inlier_mask)[0]
            best_axis_pt = axis_pt
            best_axis_dir = axis_dir
            best_radius = radius

    if len(best_inliers) < 6:
        return None

    # Compute final residual
    inlier_pts = pts[best_inliers]
    proj = inlier_pts - best_axis_pt
    along = np.dot(proj, best_axis_dir)[:, np.newaxis] * best_axis_dir
    perp = proj - along
    dist = np.linalg.norm(perp, axis=1)
    residual = float(np.mean(np.abs(dist - best_radius)))

    return {
        'type': 'CYLINDER',
        'axis_point': best_axis_pt.tolist(),
        'axis_direction': best_axis_dir.tolist(),
        'radius': float(best_radius),
        'inlier_count': len(best_inliers),
        'inlier_indices': best_inliers.tolist(),
        'residual': residual,
    }


def _sphere_from_4_points(pts):
    """Compute sphere center and radius from exactly 4 points."""
    A = np.zeros((3, 3))
    b = np.zeros(3)
    for i in range(3):
        A[i] = 2 * (pts[i + 1] - pts[0])
        b[i] = np.sum(pts[i + 1]**2 - pts[0]**2)

    try:
        center = np.linalg.solve(A, b)
        radius = np.linalg.norm(pts[0] - center)
        return center, radius
    except np.linalg.LinAlgError:
        return None, None


def detect_features_3d(points, threshold=2.0):
    """Auto-detect 3D geometric features from a point cloud.

    Tries plane, sphere, cylinder in order. Returns best fit.

    Args:
        points: Nx3 numpy array
        threshold: RANSAC inlier threshold (mm)

    Returns:
        list of detected feature dicts
    """
    pts = np.array(points, dtype=float)
    if len(pts) < 10:
        return []

    features = []
    remaining_indices = set(range(len(pts)))

    # Try to find features iteratively
    for _ in range(10):  # max 10 features
        if len(remaining_indices) < 10:
            break

        remaining_pts = pts[list(remaining_indices)]

        # Try each type and pick the one with most inliers
        candidates = []

        plane = fit_plane(remaining_pts, threshold)
        if plane and plane['inlier_count'] >= 10:
            candidates.append(plane)

        sphere = fit_sphere(remaining_pts, threshold)
        if sphere and sphere['inlier_count'] >= 10:
            candidates.append(sphere)

        cylinder = fit_cylinder(remaining_pts, threshold)
        if cylinder and cylinder['inlier_count'] >= 10:
            candidates.append(cylinder)

        if not candidates:
            break

        # Pick the best (most inliers with low residual)
        best = max(candidates, key=lambda f: f['inlier_count'])
        features.append(best)

        # Remove inlier points
        remaining_list = sorted(remaining_indices)
        for idx in best['inlier_indices']:
            if idx < len(remaining_list):
                remaining_indices.discard(remaining_list[idx])

    return features
