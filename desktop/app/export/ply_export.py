"""PLY point cloud export."""

import numpy as np


def export_ply(path, points):
    """Export 3D points as PLY file.

    Args:
        path: output file path
        points: Nx3 numpy array
    """
    pts = np.array(points, dtype=float)
    n = len(pts)

    with open(path, 'w') as f:
        # Header
        f.write("ply\n")
        f.write("format ascii 1.0\n")
        f.write(f"element vertex {n}\n")
        f.write("property float x\n")
        f.write("property float y\n")
        f.write("property float z\n")
        f.write("end_header\n")

        # Data
        for pt in pts:
            f.write(f"{pt[0]:.4f} {pt[1]:.4f} {pt[2]:.4f}\n")


def export_ply_with_mesh(path, vertices, faces):
    """Export mesh as PLY with vertices and faces.

    Args:
        path: output file path
        vertices: Nx3 numpy array
        faces: Mx3 numpy array (triangle indices)
    """
    verts = np.array(vertices, dtype=float)
    tris = np.array(faces, dtype=int)
    nv = len(verts)
    nf = len(tris)

    with open(path, 'w') as f:
        f.write("ply\n")
        f.write("format ascii 1.0\n")
        f.write(f"element vertex {nv}\n")
        f.write("property float x\n")
        f.write("property float y\n")
        f.write("property float z\n")
        f.write(f"element face {nf}\n")
        f.write("property list uchar int vertex_indices\n")
        f.write("end_header\n")

        for v in verts:
            f.write(f"{v[0]:.4f} {v[1]:.4f} {v[2]:.4f}\n")
        for face in tris:
            f.write(f"3 {face[0]} {face[1]} {face[2]}\n")
