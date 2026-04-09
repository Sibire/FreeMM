"""Point cloud to mesh reconstruction."""

import numpy as np


def points_to_mesh_delaunay(points):
    """Create a mesh from 3D points using Delaunay triangulation projected to 2D.

    Simple approach: projects points to their two most-variant axes,
    does 2D Delaunay, uses original 3D coords for vertices.

    Good for relatively flat surfaces.

    Args:
        points: Nx3 numpy array

    Returns:
        (vertices, faces) — vertices is Nx3, faces is Mx3 (triangle indices)
    """
    from scipy.spatial import Delaunay

    pts = np.array(points, dtype=float)
    if len(pts) < 4:
        return pts, np.array([])

    # Find the two axes with most variance for projection
    variances = np.var(pts, axis=0)
    axes = np.argsort(variances)[::-1][:2]
    pts_2d = pts[:, axes]

    tri = Delaunay(pts_2d)
    return pts, tri.simplices


def points_to_mesh_ball_pivot(points, radii=None):
    """Create mesh using Ball Pivoting Algorithm via Open3D.

    Args:
        points: Nx3 numpy array
        radii: list of ball radii to try. If None, auto-computed.

    Returns:
        (vertices, faces) — Nx3 and Mx3 numpy arrays
    """
    try:
        import open3d as o3d
    except ImportError:
        # Fallback to Delaunay if Open3D not installed
        return points_to_mesh_delaunay(points)

    pts = np.array(points, dtype=float)
    if len(pts) < 4:
        return pts, np.array([])

    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(pts)
    pcd.estimate_normals()

    if radii is None:
        distances = pcd.compute_nearest_neighbor_distance()
        avg_dist = np.mean(distances)
        radii = [avg_dist * 1.5, avg_dist * 3, avg_dist * 6]

    mesh = o3d.geometry.TriangleMesh.create_from_point_cloud_ball_pivoting(
        pcd, o3d.utility.DoubleVector(radii)
    )

    vertices = np.asarray(mesh.vertices)
    faces = np.asarray(mesh.triangles)
    return vertices, faces


def points_to_mesh_poisson(points, depth=8):
    """Create mesh using Poisson Surface Reconstruction via Open3D.

    Best quality but requires good normal estimation.

    Args:
        points: Nx3 numpy array
        depth: octree depth (higher = more detail, slower)

    Returns:
        (vertices, faces) — Nx3 and Mx3 numpy arrays
    """
    try:
        import open3d as o3d
    except ImportError:
        return points_to_mesh_delaunay(points)

    pts = np.array(points, dtype=float)
    if len(pts) < 10:
        return pts, np.array([])

    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(pts)
    pcd.estimate_normals()
    pcd.orient_normals_consistent_tangent_plane(k=15)

    mesh, densities = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(
        pcd, depth=depth
    )

    # Remove low-density vertices (cleanup)
    densities = np.asarray(densities)
    threshold = np.quantile(densities, 0.05)
    vertices_to_remove = densities < threshold
    mesh.remove_vertices_by_mask(vertices_to_remove)

    vertices = np.asarray(mesh.vertices)
    faces = np.asarray(mesh.triangles)
    return vertices, faces
