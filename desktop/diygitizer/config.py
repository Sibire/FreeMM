"""Constants and default configuration for DIYgitizer."""

# ---------------------------------------------------------------------------
# Link lengths (mm) — must match firmware / Fusion assembly
# ---------------------------------------------------------------------------
BASE_HEIGHT = 50.0
UPPER_ARM = 150.0
FOREARM = 130.0
WRIST_LINK = 30.0
PROBE_LEN = 20.0
BALL_RADIUS = 0.5

# ---------------------------------------------------------------------------
# Serial communication
# ---------------------------------------------------------------------------
BAUD_RATE = 115200

# ---------------------------------------------------------------------------
# Rounding
# ---------------------------------------------------------------------------
ROUNDING_OPTIONS = [1.0, 0.1, 0.01]
DEFAULT_ROUNDING = 0.1

# ---------------------------------------------------------------------------
# Joint limits (degrees) — informational, firmware enforces its own limits
# ---------------------------------------------------------------------------
JOINT_LIMITS = [
    (-180, 180),   # J1: base yaw
    (-105, 105),   # J2: shoulder pitch
    (-145, 145),   # J3: elbow pitch
    (-180, 180),   # J4: wrist pitch
    (-145, 145),   # J5: wrist roll (perpendicular)
]


def round_to(value, precision):
    """Round *value* to the nearest multiple of *precision*.

    Examples:
        round_to(3.456, 0.1)  -> 3.5
        round_to(3.456, 1.0)  -> 3.0
        round_to(3.456, 0.01) -> 3.46
    """
    if precision <= 0:
        return value
    return round(value / precision) * precision
