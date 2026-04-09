"""STL mesh export."""

import numpy as np


def export_stl(path, vertices, faces):
    """Export mesh as ASCII STL.

    Args:
        path: output file path
        vertices: Nx3 numpy array
        faces: Mx3 numpy array (triangle indices)
    """
    verts = np.array(vertices, dtype=float)
    tris = np.array(faces, dtype=int)

    with open(path, 'w') as f:
        f.write("solid DIYgitizer\n")

        for face in tris:
            v0 = verts[face[0]]
            v1 = verts[face[1]]
            v2 = verts[face[2]]

            # Compute face normal
            edge1 = v1 - v0
            edge2 = v2 - v0
            normal = np.cross(edge1, edge2)
            length = np.linalg.norm(normal)
            if length > 0:
                normal /= length
            else:
                normal = np.array([0, 0, 1])

            f.write(f"  facet normal {normal[0]:.6f} {normal[1]:.6f} {normal[2]:.6f}\n")
            f.write("    outer loop\n")
            f.write(f"      vertex {v0[0]:.6f} {v0[1]:.6f} {v0[2]:.6f}\n")
            f.write(f"      vertex {v1[0]:.6f} {v1[1]:.6f} {v1[2]:.6f}\n")
            f.write(f"      vertex {v2[0]:.6f} {v2[1]:.6f} {v2[2]:.6f}\n")
            f.write("    endloop\n")
            f.write("  endfacet\n")

        f.write("endsolid DIYgitizer\n")


def export_stl_binary(path, vertices, faces):
    """Export mesh as binary STL (smaller files).

    Args:
        path: output file path
        vertices: Nx3 numpy array
        faces: Mx3 numpy array (triangle indices)
    """
    import struct

    verts = np.array(vertices, dtype=np.float32)
    tris = np.array(faces, dtype=int)

    with open(path, 'wb') as f:
        # 80-byte header
        f.write(b'\0' * 80)
        # Number of triangles
        f.write(struct.pack('<I', len(tris)))

        for face in tris:
            v0 = verts[face[0]]
            v1 = verts[face[1]]
            v2 = verts[face[2]]

            edge1 = v1 - v0
            edge2 = v2 - v0
            normal = np.cross(edge1, edge2)
            length = np.linalg.norm(normal)
            if length > 0:
                normal /= length

            # Normal (3 floats) + 3 vertices (9 floats) + attribute byte count (1 ushort)
            f.write(struct.pack('<3f', *normal))
            f.write(struct.pack('<3f', *v0))
            f.write(struct.pack('<3f', *v1))
            f.write(struct.pack('<3f', *v2))
            f.write(struct.pack('<H', 0))
