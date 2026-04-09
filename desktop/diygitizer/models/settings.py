"""User-adjustable settings."""

from dataclasses import dataclass


@dataclass
class UserSettings:
    """Runtime settings that the user can change via the settings panel."""
    rounding_precision: float = 0.1   # mm
    ball_radius: float = 0.5          # mm
    trace_plane: str = "XY"
    trace_min_dist: float = 1.0       # mm minimum distance between trace points
