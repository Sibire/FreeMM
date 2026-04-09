"""Dimension (distance measurement) data model."""

from dataclasses import dataclass
from diygitizer.models.point import PointRecord


@dataclass
class DimensionRecord:
    """Distance between two sampled points."""
    point_a: PointRecord
    point_b: PointRecord
    distance: float
