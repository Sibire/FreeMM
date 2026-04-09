"""CSV export for CMM dimensions and points."""

import csv


def export_dimensions_csv(path, points, dimensions, dim_table=None):
    """Export dimensions list to CSV.

    Args:
        path: output file path
        points: list of (idx, np.array([x,y,z]))
        dimensions: list of (idx_a, idx_b, distance)
        dim_table: optional QTableWidget to read labels from column 3
    """
    with open(path, 'w', newline='') as f:
        writer = csv.writer(f)

        # Points section
        writer.writerow(["# Points"])
        writer.writerow(["Index", "X (mm)", "Y (mm)", "Z (mm)"])
        for idx, pt in points:
            writer.writerow([idx, f"{pt[0]:.3f}", f"{pt[1]:.3f}", f"{pt[2]:.3f}"])

        writer.writerow([])

        # Dimensions section
        writer.writerow(["# Dimensions"])
        writer.writerow(["Point A", "Point B", "Distance (mm)", "Label"])
        for i, (idx_a, idx_b, dist) in enumerate(dimensions):
            label = ""
            if dim_table and i < dim_table.rowCount():
                item = dim_table.item(i, 3)
                if item:
                    label = item.text()
            writer.writerow([f"P{idx_a}", f"P{idx_b}", f"{dist:.3f}", label])


def export_points_csv(path, points):
    """Export raw points to CSV."""
    with open(path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["Index", "X (mm)", "Y (mm)", "Z (mm)"])
        for idx, pt in points:
            writer.writerow([idx, f"{pt[0]:.3f}", f"{pt[1]:.3f}", f"{pt[2]:.3f}"])


def export_scan_csv(path, scan_points):
    """Export 3D scan points to CSV."""
    with open(path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["X (mm)", "Y (mm)", "Z (mm)"])
        for pt in scan_points:
            writer.writerow([f"{pt[0]:.3f}", f"{pt[1]:.3f}", f"{pt[2]:.3f}"])
