"""STEP export for parametric 3D features using cadquery."""

import math


def export_step(path, features):
    """Export detected 3D features as STEP parametric geometry.

    Requires cadquery to be installed: pip install cadquery

    Args:
        path: output file path
        features: list of feature dicts from detect_features_3d()
    """
    import cadquery as cq

    result = cq.Workplane("XY")
    has_geometry = False

    for feat in features:
        ftype = feat['type']

        if ftype == 'SPHERE':
            cx, cy, cz = feat['center']
            r = feat['radius']
            sphere = (cq.Workplane("XY")
                       .transformed(offset=(cx, cy, cz))
                       .sphere(r))
            if has_geometry:
                result = result.union(sphere)
            else:
                result = sphere
                has_geometry = True

        elif ftype == 'CYLINDER':
            pt = feat['axis_point']
            direction = feat['axis_direction']
            r = feat['radius']

            # Create cylinder along the detected axis
            # Default height based on inlier spread
            height = r * 4  # reasonable default

            # Compute rotation to align Z with axis direction
            dx, dy, dz = direction
            length = math.sqrt(dx*dx + dy*dy + dz*dz)
            if length < 1e-10:
                continue
            dx, dy, dz = dx/length, dy/length, dz/length

            cyl = (cq.Workplane("XY")
                    .transformed(offset=(pt[0], pt[1], pt[2] - height/2))
                    .cylinder(height, r))

            if has_geometry:
                result = result.union(cyl)
            else:
                result = cyl
                has_geometry = True

        elif ftype == 'PLANE':
            # Represent plane as a thin box at the detected location
            pt = feat['point']
            normal = feat['normal']

            box = (cq.Workplane("XY")
                    .transformed(offset=(pt[0], pt[1], pt[2]))
                    .box(100, 100, 0.5))

            if has_geometry:
                result = result.union(box)
            else:
                result = box
                has_geometry = True

    if has_geometry:
        cq.exporters.export(result, path)
    else:
        raise ValueError("No exportable features found")
