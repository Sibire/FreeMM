"""DXF export for 2D traces with dimensions via ezdxf."""

import math
import ezdxf
from ezdxf.math import Vec2


def export_trace_dxf(features, filepath, rounding=0.1):
    """Export fitted 2D features as a dimensioned DXF file.

    Args:
        features: list of fitted feature dicts, each with:
            - type: "LINE", "ARC", or "CIRCLE"
            - For LINE: start=(x,y), end=(x,y), length=float
            - For ARC: center=(x,y), radius=float, start_angle=deg, end_angle=deg
            - For CIRCLE: center=(x,y), radius=float
        filepath: output .dxf path
        rounding: dimension rounding precision in mm
    """
    doc = ezdxf.new('R2010')
    msp = doc.modelspace()

    # Set up dimension style
    doc.dimstyles.new('DIYgitizer', dxfattribs={
        'dimtxt': 2.5,      # text height
        'dimasz': 1.5,       # arrow size
        'dimgap': 0.5,       # gap between dim line and text
        'dimdec': _decimal_places(rounding),
        'dimrnd': rounding,  # round dimensions
    })

    for feat in features:
        ftype = feat['type']

        if ftype == 'LINE':
            sx, sy = feat['start']
            ex, ey = feat['end']
            msp.add_line((sx, sy), (ex, ey))

            # Add aligned dimension
            _add_line_dimension(msp, doc, feat, rounding)

        elif ftype == 'ARC':
            cx, cy = feat['center']
            r = feat['radius']
            sa = feat['start_angle']
            ea = feat['end_angle']
            msp.add_arc(
                center=(cx, cy),
                radius=r,
                start_angle=sa,
                end_angle=ea,
            )

            # Add radius dimension
            _add_radius_dimension(msp, doc, feat, rounding)

        elif ftype == 'CIRCLE':
            cx, cy = feat['center']
            r = feat['radius']
            msp.add_circle(center=(cx, cy), radius=r)

            # Add diameter dimension
            _add_diameter_dimension(msp, doc, feat, rounding)

    doc.saveas(filepath)


def _decimal_places(rounding):
    """Get number of decimal places from rounding value."""
    if rounding >= 1.0:
        return 0
    elif rounding >= 0.1:
        return 1
    else:
        return 2


def _add_line_dimension(msp, doc, feat, rounding):
    """Add an aligned dimension to a line feature."""
    sx, sy = feat['start']
    ex, ey = feat['end']

    # Offset the dimension line perpendicular to the line
    dx = ex - sx
    dy = ey - sy
    length = math.sqrt(dx * dx + dy * dy)
    if length < 0.001:
        return

    # Perpendicular offset direction
    nx = -dy / length
    ny = dx / length
    offset = 5.0  # mm offset for dimension line

    dim = msp.add_aligned_dim(
        p1=(sx, sy),
        p2=(ex, ey),
        distance=offset,
        dimstyle='DIYgitizer',
    )
    dim.render()


def _add_radius_dimension(msp, doc, feat, rounding):
    """Add a radius dimension to an arc feature."""
    cx, cy = feat['center']
    r = feat['radius']
    mid_angle = feat['start_angle'] + feat.get('sweep', 0) / 2
    if 'sweep' not in feat:
        mid_angle = (feat['start_angle'] + feat['end_angle']) / 2

    rad = math.radians(mid_angle)
    px = cx + r * math.cos(rad)
    py = cy + r * math.sin(rad)

    dim = msp.add_radius_dim(
        center=(cx, cy),
        radius=r,
        angle=mid_angle,
        dimstyle='DIYgitizer',
    )
    dim.render()


def _add_diameter_dimension(msp, doc, feat, rounding):
    """Add a diameter dimension to a circle feature."""
    cx, cy = feat['center']
    r = feat['radius']

    dim = msp.add_diameter_dim(
        center=(cx, cy),
        radius=r,
        angle=0,
        dimstyle='DIYgitizer',
    )
    dim.render()


def export_points_dxf(points, filepath):
    """Export 3D points as DXF point entities.

    Args:
        points: list of PointRecord or (x,y,z) tuples
        filepath: output .dxf path
    """
    doc = ezdxf.new('R2010')
    msp = doc.modelspace()

    for pt in points:
        if hasattr(pt, 'point'):
            msp.add_point((pt.point.x, pt.point.y, pt.point.z))
        else:
            msp.add_point(pt)

    doc.saveas(filepath)
