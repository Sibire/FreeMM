"""STL mesh export."""

import struct
import numpy as np


def export_stl_ascii(vertices, faces, filepath, solid_name="diygitizer"):
    """Export mesh as ASCII STL.

    Args:
        vertices: Nx3 numpy array
        faces: Mx3 numpy array of triangle indices
        filepath: output .stl path
        solid_name: name embedded in STL header
    """
    with open(filepath, 'w') as f:
        f.write(f"solid {solid_name}\n")

        for face in faces:
            v0 = vertices[int(face[0])]
            v1 = vertices[int(face[1])]
            v2 = vertices[int(face[2])]

            # Compute face normal
            edge1 = v1 - v0
            edge2 = v2 - v0
            normal = np.cross(edge1, edge2)
            norm_len = np.linalg.norm(normal)
            if norm_len > 0:
                normal = normal / norm_len

            f.write(f"  facet normal {normal[0]:.6e} {normal[1]:.6e} {normal[2]:.6e}\n")
            f.write("    outer loop\n")
            f.write(f"      vertex {v0[0]:.6e} {v0[1]:.6e} {v0[2]:.6e}\n")
            f.write(f"      vertex {v1[0]:.6e} {v1[1]:.6e} {v1[2]:.6e}\n")
            f.write(f"      vertex {v2[0]:.6e} {v2[1]:.6e} {v2[2]:.6e}\n")
            f.write("    endloop\n")
            f.write("  endfacet\n")

        f.write(f"endsolid {solid_name}\n")


def export_stl_binary(vertices, faces, filepath):
    """Export mesh as binary STL (more compact).

    Args:
        vertices: Nx3 numpy array
        faces: Mx3 numpy array of triangle indices
        filepath: output .stl path
    """
    num_faces = len(faces)

    with open(filepath, 'wb') as f:
        # 80-byte header
        header = b'DIYgitizer binary STL' + b'\0' * 59
        f.write(header)

        # Number of triangles
        f.write(struct.pack('<I', num_faces))

        for face in faces:
            v0 = vertices[int(face[0])]
            v1 = vertices[int(face[1])]
            v2 = vertices[int(face[2])]

            edge1 = v1 - v0
            edge2 = v2 - v0
            normal = np.cross(edge1, edge2)
            norm_len = np.linalg.norm(normal)
            if norm_len > 0:
                normal = normal / norm_len

            # Normal vector (3 floats)
            f.write(struct.pack('<3f', *normal))
            # Vertex 1, 2, 3 (3 floats each)
            f.write(struct.pack('<3f', *v0))
            f.write(struct.pack('<3f', *v1))
            f.write(struct.pack('<3f', *v2))
            # Attribute byte count
            f.write(struct.pack('<H', 0))
