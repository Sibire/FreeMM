"""Point cloud to mesh conversion using Open3D.

Open3D is an optional dependency. Falls back to a simple Delaunay approach
if Open3D is not available.
"""

import numpy as np

_open3d_available = None


def _check_open3d():
    global _open3d_available
    if _open3d_available is None:
        try:
            import open3d
            _open3d_available = True
        except ImportError:
            _open3d_available = False
    return _open3d_available


def build_mesh(points, method='ball_pivoting', depth=8, density_threshold=0.1):
    """Build a triangle mesh from a point cloud.

    Args:
        points: Nx3 numpy array
        method: 'poisson' or 'ball_pivoting' (default: ball_pivoting)
        depth: octree depth for Poisson (higher = more detail)
        density_threshold: percentile threshold for Poisson density
            trimming (0.0-1.0). Lower = more aggressive trimming.

    Returns:
        (vertices, faces) tuple of numpy arrays
        vertices: Mx3, faces: Kx3 (triangle indices)
    """
    if len(points) < 4:
        return np.empty((0, 3)), np.empty((0, 3), dtype=int)

    if not _check_open3d():
        return _fallback_mesh(points)

    import open3d as o3d

    # Create point cloud
    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(points)

    # Estimate normals — radius scaled to point cloud extent
    extent = np.ptp(points, axis=0).max()  # largest dimension
    search_radius = max(extent * 0.05, 2.0)  # 5% of extent, min 2mm
    pcd.estimate_normals(
        search_param=o3d.geometry.KDTreeSearchParamHybrid(
            radius=search_radius, max_nn=30
        )
    )
    pcd.orient_normals_consistent_tangent_plane(k=15)

    # Remove outliers
    pcd, _ = pcd.remove_statistical_outlier(nb_neighbors=20, std_ratio=2.0)

    if len(pcd.points) < 4:
        return np.empty((0, 3)), np.empty((0, 3), dtype=int)

    if method == 'poisson':
        mesh, densities = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(
            pcd, depth=depth
        )

        # Density-based trimming: remove low-density faces that Poisson
        # "invented" to close the surface.  These have no nearby points.
        densities = np.asarray(densities)
        threshold = np.quantile(densities, density_threshold)
        vertices_to_remove = densities < threshold
        mesh.remove_vertices_by_mask(vertices_to_remove)

    elif method == 'ball_pivoting':
        distances = pcd.compute_nearest_neighbor_distance()
        avg_dist = np.mean(distances)
        radii = [avg_dist * 1.5, avg_dist * 3.0, avg_dist * 6.0]
        radii = o3d.utility.DoubleVector(radii)
        mesh = o3d.geometry.TriangleMesh.create_from_point_cloud_ball_pivoting(
            pcd, radii
        )
    else:
        return _fallback_mesh(points)

    # Clean mesh
    mesh.remove_degenerate_triangles()
    mesh.remove_duplicated_triangles()
    mesh.remove_duplicated_vertices()
    mesh.remove_unreferenced_vertices()
    mesh.compute_vertex_normals()

    vertices = np.asarray(mesh.vertices)
    faces = np.asarray(mesh.triangles)

    if len(faces) == 0:
        return _fallback_mesh(points)

    return vertices, faces


def _fallback_mesh(points):
    """Simple fallback mesh using scipy Delaunay (2.5D only).

    Works for objects scanned from one side (height-map style).
    """
    from scipy.spatial import Delaunay

    if len(points) < 4:
        return np.empty((0, 3)), np.empty((0, 3), dtype=int)

    # Project to XY for triangulation, use Z as height
    tri = Delaunay(points[:, :2])
    faces = tri.simplices

    return points.copy(), faces
