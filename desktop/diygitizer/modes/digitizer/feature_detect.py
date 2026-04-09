"""3D parametric feature detection using RANSAC.

Detects simple primitives: PLANE, SPHERE, CYLINDER, CONE.
All geometry decomposes into simplest primitives with dimensioned offsets.
"""

import math
import numpy as np
from scipy.optimize import least_squares


def detect_features(points, normals=None, rounding=0.1,
                    ransac_iterations=1000, inlier_threshold=1.0,
                    min_cluster_points=20):
    """Detect parametric features in a point cloud.

    Segments the point cloud by normal similarity, then fits primitives
    to each cluster.

    Args:
        points: Nx3 numpy array
        normals: Nx3 numpy array (estimated if None)
        rounding: dimension rounding precision (mm)
        ransac_iterations: number of RANSAC iterations per fit
        inlier_threshold: max distance (mm) for inlier classification
        min_cluster_points: minimum points to attempt a fit

    Returns:
        list of feature dicts with type, parameters, inlier_indices
    """
    if len(points) < min_cluster_points:
        return []

    if normals is None:
        normals = estimate_normals(points, k=15)

    # Cluster by normal similarity
    clusters = cluster_by_normals(points, normals, angle_threshold=15.0,
                                  min_size=min_cluster_points)

    features = []
    for cluster_indices in clusters:
        cluster_pts = points[cluster_indices]
        cluster_norms = normals[cluster_indices]

        # Try fitting primitives in order of simplicity
        feat = _fit_best_primitive(cluster_pts, cluster_norms,
                                   ransac_iterations, inlier_threshold)
        if feat is not None:
            feat['inlier_indices'] = cluster_indices
            # Round dimensions
            _round_feature(feat, rounding)
            features.append(feat)

    return features


def estimate_normals(points, k=15):
    """Estimate point normals using PCA on k-nearest neighbors.

    Args:
        points: Nx3 numpy array
        k: number of neighbors

    Returns:
        Nx3 numpy array of unit normals
    """
    from scipy.spatial import cKDTree

    tree = cKDTree(points)
    normals = np.zeros_like(points)

    for i in range(len(points)):
        _, idx = tree.query(points[i], k=min(k, len(points)))
        neighbors = points[idx]
        centroid = np.mean(neighbors, axis=0)
        centered = neighbors - centroid
        _, _, Vt = np.linalg.svd(centered, full_matrices=False)
        normal = Vt[2]  # smallest singular value direction

        # Orient normals consistently (pointing away from centroid of all points)
        center = np.mean(points, axis=0)
        if np.dot(normal, points[i] - center) < 0:
            normal = -normal

        normals[i] = normal

    return normals


def cluster_by_normals(points, normals, angle_threshold=15.0, min_size=20):
    """Cluster points by normal similarity using region growing.

    Args:
        points: Nx3 numpy array
        normals: Nx3 numpy array
        angle_threshold: max angle (degrees) between normals in same cluster
        min_size: minimum cluster size

    Returns:
        list of numpy arrays of indices
    """
    from scipy.spatial import cKDTree

    n = len(points)
    tree = cKDTree(points)
    visited = np.zeros(n, dtype=bool)
    clusters = []
    cos_threshold = math.cos(math.radians(angle_threshold))

    for seed in range(n):
        if visited[seed]:
            continue

        # Region growing from seed
        cluster = []
        queue = [seed]
        visited[seed] = True
        seed_normal = normals[seed]

        while queue:
            current = queue.pop(0)
            cluster.append(current)

            # Find spatial neighbors
            neighbors = tree.query_ball_point(points[current], r=5.0)
            for nb in neighbors:
                if visited[nb]:
                    continue
                # Check normal similarity with seed
                cos_angle = np.dot(normals[nb], seed_normal)
                if cos_angle >= cos_threshold:
                    visited[nb] = True
                    queue.append(nb)

        if len(cluster) >= min_size:
            clusters.append(np.array(cluster))

    return clusters


def fit_plane_ransac(points, iterations=1000, threshold=1.0):
    """Fit a plane using RANSAC.

    Args:
        points: Nx3 numpy array
        iterations: RANSAC iterations
        threshold: inlier distance threshold (mm)

    Returns:
        dict with type="PLANE", normal, point, offset, bounds, inlier_ratio
        or None if fit is poor
    """
    n = len(points)
    if n < 3:
        return None

    best_inliers = 0
    best_normal = None
    best_d = None

    for _ in range(iterations):
        # Random 3 points
        idx = np.random.choice(n, 3, replace=False)
        p0, p1, p2 = points[idx]

        v1 = p1 - p0
        v2 = p2 - p0
        normal = np.cross(v1, v2)
        norm_len = np.linalg.norm(normal)
        if norm_len < 1e-10:
            continue
        normal = normal / norm_len
        d = np.dot(normal, p0)

        # Count inliers
        distances = np.abs(np.dot(points, normal) - d)
        num_inliers = np.sum(distances < threshold)

        if num_inliers > best_inliers:
            best_inliers = num_inliers
            best_normal = normal
            best_d = d

    if best_normal is None or best_inliers < 0.5 * n:
        return None

    # Refine with all inliers
    distances = np.abs(np.dot(points, best_normal) - best_d)
    inlier_mask = distances < threshold
    inlier_pts = points[inlier_mask]

    centroid = np.mean(inlier_pts, axis=0)
    centered = inlier_pts - centroid
    _, _, Vt = np.linalg.svd(centered, full_matrices=False)
    normal = Vt[2]

    # Compute bounds (width, height in plane coordinates)
    u = Vt[0]
    v = Vt[1]
    proj_u = centered @ u
    proj_v = centered @ v
    w = np.max(proj_u) - np.min(proj_u)
    h = np.max(proj_v) - np.min(proj_v)

    rms = np.sqrt(np.mean(distances[inlier_mask] ** 2))

    return {
        'type': 'PLANE',
        'normal': tuple(normal),
        'point': tuple(centroid),
        'offset': float(np.dot(normal, centroid)),
        'bounds': (float(w), float(h)),
        'rms_error': float(rms),
        'inlier_ratio': best_inliers / n,
    }


def fit_sphere_ransac(points, iterations=1000, threshold=1.0):
    """Fit a sphere using RANSAC.

    Args:
        points: Nx3 numpy array
        iterations: RANSAC iterations
        threshold: inlier distance threshold (mm)

    Returns:
        dict with type="SPHERE", center, radius, rms_error, inlier_ratio
        or None
    """
    n = len(points)
    if n < 4:
        return None

    best_inliers = 0
    best_center = None
    best_radius = None

    for _ in range(iterations):
        idx = np.random.choice(n, 4, replace=False)
        sample = points[idx]

        # Solve for sphere through 4 points
        center, radius = _sphere_from_4_points(sample)
        if center is None:
            continue

        distances = np.abs(np.linalg.norm(points - center, axis=1) - radius)
        num_inliers = np.sum(distances < threshold)

        if num_inliers > best_inliers:
            best_inliers = num_inliers
            best_center = center
            best_radius = radius

    if best_center is None or best_inliers < 0.5 * n:
        return None

    # Refine
    def residuals(params):
        cx, cy, cz, r = params
        dists = np.sqrt((points[:, 0] - cx)**2 + (points[:, 1] - cy)**2 +
                        (points[:, 2] - cz)**2)
        return dists - r

    result = least_squares(residuals,
                           [*best_center, best_radius])
    cx, cy, cz, r = result.x

    distances = np.abs(np.linalg.norm(points - np.array([cx, cy, cz]), axis=1) - abs(r))
    rms = np.sqrt(np.mean(distances ** 2))

    return {
        'type': 'SPHERE',
        'center': (float(cx), float(cy), float(cz)),
        'radius': float(abs(r)),
        'rms_error': float(rms),
        'inlier_ratio': best_inliers / n,
    }


def fit_cylinder_ransac(points, normals, iterations=1000, threshold=1.0):
    """Fit a cylinder using RANSAC.

    Args:
        points: Nx3 numpy array
        normals: Nx3 numpy array
        iterations: RANSAC iterations
        threshold: inlier distance threshold (mm)

    Returns:
        dict with type="CYLINDER", center, axis, radius, height, rms_error
        or None
    """
    n = len(points)
    if n < 6:
        return None

    best_inliers = 0
    best_axis = None
    best_point_on_axis = None
    best_radius = None

    for _ in range(iterations):
        # Pick 2 random points, use cross product of their normals as axis estimate
        idx = np.random.choice(n, 2, replace=False)
        axis = np.cross(normals[idx[0]], normals[idx[1]])
        axis_len = np.linalg.norm(axis)
        if axis_len < 1e-10:
            continue
        axis = axis / axis_len

        # Project points onto plane perpendicular to axis
        projections = points - np.outer(np.dot(points, axis), axis)

        # Fit circle in 2D (project onto a plane)
        centroid = np.mean(projections, axis=0)
        dists_from_center = np.linalg.norm(projections - centroid, axis=1)
        radius = np.median(dists_from_center)

        # Count inliers
        errors = np.abs(dists_from_center - radius)
        num_inliers = np.sum(errors < threshold)

        if num_inliers > best_inliers:
            best_inliers = num_inliers
            best_axis = axis
            best_point_on_axis = centroid
            best_radius = radius

    if best_axis is None or best_inliers < 0.4 * n:
        return None

    # Compute height (extent along axis)
    axis_projections = np.dot(points, best_axis)
    height = np.max(axis_projections) - np.min(axis_projections)
    center_along = (np.max(axis_projections) + np.min(axis_projections)) / 2
    center = best_point_on_axis + center_along * best_axis

    # Compute RMS
    perpendicular = points - np.outer(np.dot(points, best_axis), best_axis)
    centroid = np.mean(perpendicular, axis=0)
    dists = np.linalg.norm(perpendicular - centroid, axis=1)
    rms = np.sqrt(np.mean((dists - best_radius) ** 2))

    return {
        'type': 'CYLINDER',
        'center': tuple(center),
        'axis': tuple(best_axis),
        'radius': float(best_radius),
        'height': float(height),
        'rms_error': float(rms),
        'inlier_ratio': best_inliers / n,
    }


def _fit_best_primitive(points, normals, iterations, threshold):
    """Try fitting primitives in order of simplicity, return best fit."""
    # Check normal variance to guide fitting
    normal_variance = np.var(normals, axis=0).sum()

    results = []

    # Always try plane
    plane = fit_plane_ransac(points, iterations, threshold)
    if plane and plane['inlier_ratio'] > 0.8:
        results.append(plane)

    # Try sphere if normals vary significantly
    if normal_variance > 0.1:
        sphere = fit_sphere_ransac(points, iterations, threshold)
        if sphere and sphere['inlier_ratio'] > 0.7:
            results.append(sphere)

    # Try cylinder if normals have some structure
    if normal_variance > 0.05:
        cylinder = fit_cylinder_ransac(points, normals, iterations, threshold)
        if cylinder and cylinder['inlier_ratio'] > 0.6:
            results.append(cylinder)

    if not results:
        return None

    # Pick the one with lowest RMS error
    return min(results, key=lambda f: f['rms_error'])


def _sphere_from_4_points(pts):
    """Compute sphere through 4 points. Returns (center, radius) or (None, None)."""
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


def _round_feature(feat, rounding):
    """Round dimensions in a feature dict."""
    rv = lambda v: round(v / rounding) * rounding if rounding > 0 else v

    if feat['type'] == 'PLANE':
        feat['bounds'] = (rv(feat['bounds'][0]), rv(feat['bounds'][1]))
        feat['point'] = tuple(rv(v) for v in feat['point'])

    elif feat['type'] == 'SPHERE':
        feat['radius'] = rv(feat['radius'])
        feat['center'] = tuple(rv(v) for v in feat['center'])

    elif feat['type'] == 'CYLINDER':
        feat['radius'] = rv(feat['radius'])
        feat['height'] = rv(feat['height'])
        feat['center'] = tuple(rv(v) for v in feat['center'])

    elif feat['type'] == 'CONE':
        feat['height'] = rv(feat.get('height', 0))
        if 'apex' in feat:
            feat['apex'] = tuple(rv(v) for v in feat['apex'])
