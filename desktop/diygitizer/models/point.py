"""Point and point-record data models."""

import time
from dataclasses import dataclass, field


@dataclass
class Point3D:
    """A simple 3D coordinate."""
    x: float
    y: float
    z: float

    def as_tuple(self):
        """Return (x, y, z) tuple."""
        return (self.x, self.y, self.z)


@dataclass
class PointRecord:
    """A sampled point with metadata."""
    index: int
    point: Point3D
    timestamp: float = field(default_factory=time.time)

    @property
    def x(self):
        return self.point.x

    @property
    def y(self):
        return self.point.y

    @property
    def z(self):
        return self.point.z
