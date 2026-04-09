"""DXF export with dimensions via ezdxf."""

import math
import ezdxf
from ezdxf.enums import TextEntityAlignment


def export_trace_dxf(path, pipeline_result):
    """Export 2D trace features and dimensions to DXF.

    Args:
        path: output file path
        pipeline_result: dict from run_pipeline()
    """
    doc = ezdxf.new('R2010')
    msp = doc.modelspace()

    # Add dimension style
    doc.dimstyles.new('DIYgitizer', dxfattribs={
        'dimtxt': 2.5,      # text height
        'dimasz': 2.0,      # arrow size
        'dimgap': 1.0,      # gap between text and line
        'dimclrd': 1,       # dimension line color (red)
        'dimclrt': 1,       # text color (red)
    })

    # Draw features
    features = pipeline_result.get('features', [])
    for feat in features:
        ftype = feat['type']

        if ftype == 'LINE':
            p1 = feat['start']
            p2 = feat['end']
            msp.add_line(p1, p2, dxfattribs={'layer': 'Geometry', 'color': 5})

            # Add linear dimension
            length = feat['length']
            dx = p2[0] - p1[0]
            dy = p2[1] - p1[1]
            # Offset the dimension line perpendicular to the feature
            angle = math.atan2(dy, dx)
            offset = 5.0  # mm offset for dimension line
            nx = -math.sin(angle) * offset
            ny = math.cos(angle) * offset
            dim_point = ((p1[0] + p2[0]) / 2 + nx,
                         (p1[1] + p2[1]) / 2 + ny)

            msp.add_aligned_dim(
                p1=p1, p2=p2,
                distance=offset,
                dimstyle='DIYgitizer',
                override={'dimtxt': 2.5},
            ).render()

        elif ftype == 'ARC':
            cx, cy = feat['center']
            r = feat['radius']
            start_deg = feat['start_angle']
            span_deg = feat['span_angle']
            end_deg = start_deg + span_deg

            msp.add_arc(
                center=(cx, cy),
                radius=r,
                start_angle=start_deg,
                end_angle=end_deg,
                dxfattribs={'layer': 'Geometry', 'color': 5},
            )

            # Add radius dimension
            angle_mid = math.radians((start_deg + end_deg) / 2)
            dim_point = (cx + r * math.cos(angle_mid),
                         cy + r * math.sin(angle_mid))
            msp.add_radius_dim(
                center=(cx, cy),
                radius=r,
                angle=math.degrees(angle_mid),
                dimstyle='DIYgitizer',
            ).render()

        elif ftype == 'CIRCLE':
            cx, cy = feat['center']
            r = feat['radius']

            msp.add_circle(
                center=(cx, cy),
                radius=r,
                dxfattribs={'layer': 'Geometry', 'color': 5},
            )

            # Add diameter dimension
            msp.add_diameter_dim(
                center=(cx, cy),
                radius=r,
                angle=45,
                dimstyle='DIYgitizer',
            ).render()

    # Also draw raw trace as reference on a separate layer
    raw = pipeline_result.get('raw', [])
    if len(raw) > 1:
        points = [tuple(p) for p in raw]
        msp.add_lwpolyline(points, dxfattribs={'layer': 'RawTrace', 'color': 8})

    doc.saveas(path)
