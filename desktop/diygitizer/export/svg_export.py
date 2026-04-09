"""SVG export for 2D traces with dimensions."""

import math


def export_trace_svg(features, filepath, rounding=0.1, margin=20, scale=1.0):
    """Export fitted 2D features as SVG with dimension annotations.

    Args:
        features: list of fitted feature dicts (same format as dxf_export)
        filepath: output .svg path
        rounding: dimension rounding precision
        margin: margin around drawing in SVG units
        scale: scale factor (mm to SVG units)
    """
    if not features:
        return

    # Compute bounding box
    all_points = _collect_all_points(features)
    if not all_points:
        return

    min_x = min(p[0] for p in all_points)
    max_x = max(p[0] for p in all_points)
    min_y = min(p[1] for p in all_points)
    max_y = max(p[1] for p in all_points)

    width = (max_x - min_x) * scale + 2 * margin
    height = (max_y - min_y) * scale + 2 * margin

    def tx(x):
        return (x - min_x) * scale + margin

    def ty(y):
        return height - ((y - min_y) * scale + margin)  # flip Y

    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" '
                 f'width="{width:.1f}" height="{height:.1f}" '
                 f'viewBox="0 0 {width:.1f} {height:.1f}">')
    lines.append('<style>')
    lines.append('  .geom { stroke: black; stroke-width: 0.5; fill: none; }')
    lines.append('  .dim-line { stroke: #666; stroke-width: 0.3; fill: none; }')
    lines.append('  .dim-text { font-family: Arial; font-size: 3px; fill: #333; '
                 'text-anchor: middle; }')
    lines.append('  .dim-arrow { fill: #666; }')
    lines.append('</style>')

    dim_offset = 5.0 * scale
    dec = _decimal_places(rounding)

    for feat in features:
        ftype = feat['type']

        if ftype == 'LINE':
            sx, sy = feat['start']
            ex, ey = feat['end']
            lines.append(f'<line class="geom" '
                         f'x1="{tx(sx):.2f}" y1="{ty(sy):.2f}" '
                         f'x2="{tx(ex):.2f}" y2="{ty(ey):.2f}" />')

            # Dimension annotation
            length = feat.get('length', math.dist(feat['start'], feat['end']))
            rounded_len = _round_val(length, rounding)
            mid_x = (tx(sx) + tx(ex)) / 2
            mid_y = (ty(sy) + ty(ey)) / 2 - 3
            lines.append(f'<text class="dim-text" x="{mid_x:.2f}" y="{mid_y:.2f}">'
                         f'{rounded_len:.{dec}f}</text>')

        elif ftype == 'ARC':
            cx, cy = feat['center']
            r = feat['radius'] * scale
            sa = math.radians(feat['start_angle'])
            ea = math.radians(feat['end_angle'])

            sx_a = tx(cx + feat['radius'] * math.cos(sa))
            sy_a = ty(cy + feat['radius'] * math.sin(sa))
            ex_a = tx(cx + feat['radius'] * math.cos(ea))
            ey_a = ty(cy + feat['radius'] * math.sin(ea))

            sweep = feat['end_angle'] - feat['start_angle']
            if sweep < 0:
                sweep += 360
            large_arc = 1 if sweep > 180 else 0

            lines.append(f'<path class="geom" d="M {sx_a:.2f} {sy_a:.2f} '
                         f'A {r:.2f} {r:.2f} 0 {large_arc} 0 '
                         f'{ex_a:.2f} {ey_a:.2f}" />')

            # Radius annotation
            rounded_r = _round_val(feat['radius'], rounding)
            lines.append(f'<text class="dim-text" x="{tx(cx):.2f}" '
                         f'y="{ty(cy) - 3:.2f}">R{rounded_r:.{dec}f}</text>')

        elif ftype == 'CIRCLE':
            cx, cy = feat['center']
            r = feat['radius'] * scale
            lines.append(f'<circle class="geom" cx="{tx(cx):.2f}" '
                         f'cy="{ty(cy):.2f}" r="{r:.2f}" />')

            # Diameter annotation
            rounded_d = _round_val(feat['radius'] * 2, rounding)
            lines.append(f'<text class="dim-text" x="{tx(cx):.2f}" '
                         f'y="{ty(cy) - r - 3:.2f}">⌀{rounded_d:.{dec}f}</text>')

    lines.append('</svg>')

    with open(filepath, 'w') as f:
        f.write('\n'.join(lines))


def _collect_all_points(features):
    """Collect all relevant points from features for bounding box."""
    pts = []
    for feat in features:
        ftype = feat['type']
        if ftype == 'LINE':
            pts.append(feat['start'])
            pts.append(feat['end'])
        elif ftype in ('ARC', 'CIRCLE'):
            cx, cy = feat['center']
            r = feat['radius']
            pts.append((cx - r, cy - r))
            pts.append((cx + r, cy + r))
    return pts


def _decimal_places(rounding):
    if rounding >= 1.0:
        return 0
    elif rounding >= 0.1:
        return 1
    return 2


def _round_val(value, rounding):
    if rounding <= 0:
        return value
    return round(value / rounding) * rounding
