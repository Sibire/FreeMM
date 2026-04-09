"""2D trace session data model."""

from dataclasses import dataclass, field
from typing import List, Tuple


@dataclass
class TraceSession:
    """A 2D trace recording session.

    *plane* is one of "XY", "XZ", "YZ".
    *points* stores (a, b) tuples projected onto the chosen plane.
    *features* is populated later by the feature-fitting pipeline.
    """
    plane: str = "XY"
    points: List[Tuple[float, float]] = field(default_factory=list)
    features: list = field(default_factory=list)
