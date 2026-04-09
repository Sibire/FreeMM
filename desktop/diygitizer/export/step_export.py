"""STEP export for parametric 3D features via CadQuery.

CadQuery is an optional dependency (~500MB). This module uses lazy imports
and provides clear error messages if CadQuery is not installed.
"""

import math

_cadquery_available = None


def _check_cadquery():
    global _cadquery_available
    if _cadquery_available is None:
        try:
            import cadquery
            _cadquery_available = True
        except ImportError:
            _cadquery_available = False
    return _cadquery_available


def export_features_step(features, filepath, rounding=0.1):
    """Export detected 3D features as a STEP file with parametric geometry.

    Each feature becomes a simple solid positioned by its fitted parameters.
    When opened in Fusion 360, each dimension is individually editable.

    Args:
        features: list of feature dicts, each with:
            - type: "PLANE", "CYLINDER", "SPHERE", "CONE"
            - For PLANE: normal=(nx,ny,nz), point=(x,y,z), bounds=(w,h)
            - For CYLINDER: center=(x,y,z), axis=(ax,ay,az), radius=float, height=float
            - For SPHERE: center=(x,y,z), radius=float
            - For CONE: apex=(x,y,z), axis=(ax,ay,az), half_angle=deg, height=float
        filepath: output .step path
        rounding: dimension rounding precision in mm
    """
    if not _check_cadquery():
        raise ImportError(
            "CadQuery is required for STEP export. Install with:\n"
            "  pip install cadquery\n"
            "This is a large package (~500MB). Point cloud (PLY) and mesh (STL) "
            "export work without it."
        )

    import cadquery as cq

    assembly = cq.Assembly()

    for i, feat in enumerate(features):
        ftype = feat['type']
        solid = None

        if ftype == 'PLANE':
            w, h = feat.get('bounds', (50, 50))
            w = _round_val(w, rounding)
            h = _round_val(h, rounding)
            thickness = 1.0  # thin slab representing the plane
            solid = cq.Workplane("XY").box(w, h, thickness)
            px, py, pz = feat['point']
            solid = solid.translate((px, py, pz))

        elif ftype == 'CYLINDER':
            r = _round_val(feat['radius'], rounding)
            height = _round_val(feat['height'], rounding)
            solid = cq.Workplane("XY").circle(r).extrude(height)
            cx, cy, cz = feat['center']
            solid = solid.translate((cx, cy, cz))

        elif ftype == 'SPHERE':
            r = _round_val(feat['radius'], rounding)
            solid = cq.Workplane("XY").sphere(r)
            cx, cy, cz = feat['center']
            solid = solid.translate((cx, cy, cz))

        elif ftype == 'CONE':
            r_base = _round_val(
                feat['height'] * math.tan(math.radians(feat['half_angle'])),
                rounding
            )
            height = _round_val(feat['height'], rounding)
            solid = (cq.Workplane("XY")
                     .circle(r_base)
                     .workplane(offset=height)
                     .circle(0.001)  # near-zero top for cone
                     .loft())
            ax, ay, az = feat.get('apex', (0, 0, 0))
            solid = solid.translate((ax, ay, az))

        if solid is not None:
            assembly.add(solid, name=f"{ftype.lower()}_{i}")

    cq.exporters.export(assembly.toCompound(), filepath)


def _round_val(value, rounding):
    if rounding <= 0:
        return value
    return round(value / rounding) * rounding
