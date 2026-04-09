"""CMM dimension report export (CSV and text)."""

import csv
import os
from datetime import datetime


def export_dimensions_csv(dimensions, filepath):
    """Export dimension list as CSV.

    Args:
        dimensions: list of DimensionRecord objects
        filepath: output file path (.csv)
    """
    with open(filepath, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            'Dimension #',
            'Point A Index', 'A_X (mm)', 'A_Y (mm)', 'A_Z (mm)',
            'Point B Index', 'B_X (mm)', 'B_Y (mm)', 'B_Z (mm)',
            'Distance (mm)'
        ])
        for i, dim in enumerate(dimensions, 1):
            a = dim.point_a
            b = dim.point_b
            writer.writerow([
                i,
                a.index, f'{a.point.x:.3f}', f'{a.point.y:.3f}', f'{a.point.z:.3f}',
                b.index, f'{b.point.x:.3f}', f'{b.point.y:.3f}', f'{b.point.z:.3f}',
                f'{dim.distance:.3f}'
            ])


def export_points_csv(points, filepath):
    """Export captured points as CSV.

    Args:
        points: list of PointRecord objects
        filepath: output file path (.csv)
    """
    with open(filepath, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Point #', 'X (mm)', 'Y (mm)', 'Z (mm)', 'Timestamp'])
        for pt in points:
            writer.writerow([
                pt.index,
                f'{pt.point.x:.3f}',
                f'{pt.point.y:.3f}',
                f'{pt.point.z:.3f}',
                f'{pt.timestamp:.3f}'
            ])


def export_report_text(points, dimensions, filepath):
    """Export full CMM report as text file.

    Args:
        points: list of PointRecord objects
        dimensions: list of DimensionRecord objects
        filepath: output file path (.txt)
    """
    with open(filepath, 'w') as f:
        f.write("DIYgitizer CMM Report\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 60 + "\n\n")

        f.write(f"Captured Points: {len(points)}\n")
        f.write("-" * 40 + "\n")
        for pt in points:
            f.write(f"  P{pt.index}: ({pt.point.x:.3f}, {pt.point.y:.3f}, {pt.point.z:.3f})\n")

        f.write(f"\nDimensions: {len(dimensions)}\n")
        f.write("-" * 40 + "\n")
        for i, dim in enumerate(dimensions, 1):
            f.write(f"  D{i}: P{dim.point_a.index} → P{dim.point_b.index} = {dim.distance:.3f} mm\n")
