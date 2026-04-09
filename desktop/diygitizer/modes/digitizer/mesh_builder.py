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


def build_mesh(points, method='poisson', depth=8, ball_radius_factor=2.0):
    """Build a triangle mesh from a point cloud.

    Args:
        points: Nx3 numpy array
        method: 'poisson' or 'ball_pivoting'
        depth: octree depth for Poisson (higher = more detail)
        ball_radius_factor: ball radius multiplier for BPA

    Returns:
        (vertices, faces) tuple of numpy arrays
        vertices: Mx3, faces: Kx3 (triangle indices)
    """
    if not _check_open3d():
        return _fallback_mesh(points)

    import open3d as o3d

    # Create point cloud
    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(points)

    # Estimate normals
    pcd.estimate_normals(
        search_param=o3d.geometry.KDTreeSearchParamHybrid(radius=10.0, max_nn=30)
    )
    pcd.orient_normals_consistent_tangent_plane(k=15)

    # Remove outliers
    pcd, _ = pcd.remove_statistical_outlier(nb_neighbors=20, std_ratio=2.0)

    if method == 'poisson':
        mesh, densities = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(
            pcd, depth=depth
        )

        # Crop to bounding box of original points (Poisson creates extra surface)
        bbox = pcd.get_axis_aligned_bounding_box()
        bbox = bbox.scale(1.1, bbox.get_center())  # slight margin
        mesh = mesh.crop(bbox)

    elif method == 'ball_pivoting':
        distances = pcd.compute_nearest_neighbor_distance()
        avg_dist = np.mean(distances)
        radii = [avg_dist * ball_radius_factor,
                 avg_dist * ball_radius_factor * 2]
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
    mesh.compute_vertex_normals()

    vertices = np.asarray(mesh.vertices)
    faces = np.asarray(mesh.triangles)

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
