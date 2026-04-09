"""PLY and CSV point cloud export."""

import csv
import numpy as np


def export_ply(points, filepath, normals=None):
    """Export point cloud as PLY file.

    Args:
        points: Nx3 numpy array of XYZ coordinates
        filepath: output .ply path
        normals: optional Nx3 numpy array of normal vectors
    """
    n = len(points)
    has_normals = normals is not None and len(normals) == n

    with open(filepath, 'w') as f:
        f.write("ply\n")
        f.write("format ascii 1.0\n")
        f.write(f"element vertex {n}\n")
        f.write("property float x\n")
        f.write("property float y\n")
        f.write("property float z\n")
        if has_normals:
            f.write("property float nx\n")
            f.write("property float ny\n")
            f.write("property float nz\n")
        f.write("end_header\n")

        for i in range(n):
            x, y, z = points[i]
            line = f"{x:.6f} {y:.6f} {z:.6f}"
            if has_normals:
                nx, ny, nz = normals[i]
                line += f" {nx:.6f} {ny:.6f} {nz:.6f}"
            f.write(line + "\n")


def export_points_csv(points, filepath):
    """Export point cloud as CSV.

    Args:
        points: Nx3 numpy array or list of (x,y,z)
        filepath: output .csv path
    """
    with open(filepath, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['X', 'Y', 'Z'])
        for pt in points:
            writer.writerow([f'{pt[0]:.6f}', f'{pt[1]:.6f}', f'{pt[2]:.6f}'])


def export_ply_with_mesh(vertices, faces, filepath):
    """Export mesh as PLY with vertices and faces.

    Args:
        vertices: Nx3 numpy array
        faces: Mx3 numpy array of triangle indices
        filepath: output .ply path
    """
    nv = len(vertices)
    nf = len(faces)

    with open(filepath, 'w') as f:
        f.write("ply\n")
        f.write("format ascii 1.0\n")
        f.write(f"element vertex {nv}\n")
        f.write("property float x\n")
        f.write("property float y\n")
        f.write("property float z\n")
        f.write(f"element face {nf}\n")
        f.write("property list uchar int vertex_indices\n")
        f.write("end_header\n")

        for v in vertices:
            f.write(f"{v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n")

        for face in faces:
            f.write(f"3 {int(face[0])} {int(face[1])} {int(face[2])}\n")
