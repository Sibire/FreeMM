"""SVG export for 2D trace features and dimensions."""

import math
import xml.etree.ElementTree as ET


def export_trace_svg(path, pipeline_result, margin=20, scale=2.0):
    """Export 2D trace features and dimensions to SVG.

    Args:
        path: output file path
        pipeline_result: dict from run_pipeline()
        margin: margin around content (px)
        scale: mm to px scale factor
    """
    features = pipeline_result.get('features', [])
    raw = pipeline_result.get('raw', [])
    dimensions = pipeline_result.get('dimensions', [])

    # Compute bounding box
    all_pts = []
    for feat in features:
        if feat['type'] == 'LINE':
            all_pts.extend([feat['start'], feat['end']])
        elif feat['type'] in ('ARC', 'CIRCLE'):
            cx, cy = feat['center']
            r = feat['radius']
            all_pts.extend([(cx - r, cy - r), (cx + r, cy + r)])
    if raw is not None and len(raw) > 0:
        all_pts.extend([tuple(p) for p in raw])

    if not all_pts:
        return

    xs = [p[0] for p in all_pts]
    ys = [p[1] for p in all_pts]
    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)

    width = (x_max - x_min) * scale + 2 * margin
    height = (y_max - y_min) * scale + 2 * margin

    def tx(x):
        return (x - x_min) * scale + margin

    def ty(y):
        # Flip Y for SVG (Y increases downward)
        return height - ((y - y_min) * scale + margin)

    # Build SVG
    svg = ET.Element('svg', xmlns='http://www.w3.org/2000/svg',
                     width=str(int(width)), height=str(int(height)),
                     viewBox=f"0 0 {int(width)} {int(height)}")

    # Background
    ET.SubElement(svg, 'rect', width='100%', height='100%', fill='white')

    # Raw trace (gray, thin)
    if raw is not None and len(raw) > 1:
        points_str = " ".join(f"{tx(p[0]):.1f},{ty(p[1]):.1f}" for p in raw)
        ET.SubElement(svg, 'polyline', points=points_str,
                      fill='none', stroke='#cccccc', **{'stroke-width': '0.5'})

    # Features (blue)
    for feat in features:
        if feat['type'] == 'LINE':
            p1, p2 = feat['start'], feat['end']
            ET.SubElement(svg, 'line',
                          x1=f"{tx(p1[0]):.1f}", y1=f"{ty(p1[1]):.1f}",
                          x2=f"{tx(p2[0]):.1f}", y2=f"{ty(p2[1]):.1f}",
                          stroke='#3278DC', **{'stroke-width': '2'})

        elif feat['type'] == 'CIRCLE':
            cx, cy = feat['center']
            r = feat['radius']
            ET.SubElement(svg, 'circle',
                          cx=f"{tx(cx):.1f}", cy=f"{ty(cy):.1f}",
                          r=f"{r * scale:.1f}",
                          fill='none', stroke='#3278DC', **{'stroke-width': '2'})

        elif feat['type'] == 'ARC':
            cx, cy = feat['center']
            r = feat['radius']
            sa = math.radians(feat['start_angle'])
            span = math.radians(feat['span_angle'])
            ea = sa + span

            x1 = cx + r * math.cos(sa)
            y1 = cy + r * math.sin(sa)
            x2 = cx + r * math.cos(ea)
            y2 = cy + r * math.sin(ea)

            large_arc = 1 if abs(span) > math.pi else 0
            sweep = 1 if span > 0 else 0

            rs = r * scale
            d = (f"M {tx(x1):.1f} {ty(y1):.1f} "
                 f"A {rs:.1f} {rs:.1f} 0 {large_arc} {1-sweep} "
                 f"{tx(x2):.1f} {ty(y2):.1f}")
            ET.SubElement(svg, 'path', d=d,
                          fill='none', stroke='#3278DC', **{'stroke-width': '2'})

    # Dimensions (red text)
    for dim in dimensions:
        if dim['type'] == 'LINEAR':
            p1, p2 = dim['start'], dim['end']
            mx = (tx(p1[0]) + tx(p2[0])) / 2
            my = (ty(p1[1]) + ty(p2[1])) / 2
            text = ET.SubElement(svg, 'text', x=f"{mx:.1f}", y=f"{my - 5:.1f}",
                                 fill='#C83C3C', **{'font-size': '10', 'text-anchor': 'middle'})
            text.text = f"{dim['value']:.1f}"

        elif dim['type'] == 'RADIUS':
            cx, cy = dim['center']
            r = dim['radius']
            text = ET.SubElement(svg, 'text',
                                 x=f"{tx(cx) + r * scale * 0.5:.1f}",
                                 y=f"{ty(cy) - 5:.1f}",
                                 fill='#C83C3C', **{'font-size': '10'})
            text.text = f"R{r:.1f}"

    tree = ET.ElementTree(svg)
    ET.indent(tree, space='  ')
    tree.write(path, xml_declaration=True, encoding='utf-8')
