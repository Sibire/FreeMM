"""Built-in simulator connection — no hardware required.

Three simulator modes:
  - MANUAL: Joint angles controlled by sliders in the UI. Arm stays put.
  - IDLE: Gentle sine-wave oscillation (default on connect, for demo).
  - SHAPE: Traces a predefined test shape (rectangle, circle, cylinder,
    sphere) by computing probe-tip positions along the shape surface
    and approximate IK to produce realistic joint angles.

Speaks the same line-based protocol as the real firmware.
"""

import math
import time
import threading

from diygitizer.config import (
    BASE_HEIGHT,
    UPPER_ARM,
    FOREARM,
    WRIST_LINK,
    PROBE_LEN,
)
from diygitizer.connection.base import ArmConnection

# ── Forward kinematics (mirrors firmware) ──────────────────────────────

def _sim_fk(j1d, j2d, j3d, j4d, j5d):
    """Lightweight FK using only the math module."""
    j1 = math.radians(j1d)
    j2 = math.radians(j2d)
    j3 = math.radians(j3d)
    j4 = math.radians(j4d)
    j5 = math.radians(j5d)

    c1, s1 = math.cos(j1), math.sin(j1)

    ex = UPPER_ARM * math.cos(j2) * c1
    ey = UPPER_ARM * math.cos(j2) * s1
    ez = BASE_HEIGHT + UPPER_ARM * math.sin(j2)

    p23 = j2 + j3
    wx = ex + FOREARM * math.cos(p23) * c1
    wy = ey + FOREARM * math.cos(p23) * s1
    wz = ez + FOREARM * math.sin(p23)

    p234 = p23 + j4
    cp, sp = math.cos(p234), math.sin(p234)
    jx = wx + WRIST_LINK * cp * c1
    jy = wy + WRIST_LINK * cp * s1
    jz = wz + WRIST_LINK * sp

    fx, fy, fz = cp * c1, cp * s1, sp
    lx, ly = -s1, c1

    c5, s5 = math.cos(j5), math.sin(j5)
    dx = c5 * fx + s5 * lx
    dy = c5 * fy + s5 * ly
    dz = c5 * fz

    return jx + PROBE_LEN * dx, jy + PROBE_LEN * dy, jz + PROBE_LEN * dz


# ── Approximate inverse kinematics ────────────────────────────────────

_TOOL = WRIST_LINK + PROBE_LEN   # tool length beyond forearm

def _approx_ik(x, y, z):
    """Compute approximate joint angles (degrees) to reach (x, y, z).

    Returns (j1, j2, j3, j4, j5) in degrees.  J5 is always 0.

    Strategy: choose J4 so the tool (wrist link + probe) points
    horizontally.  That means pitch234 = 0, so the tool extends
    radially outward from the base axis.  Then solve 2-link IK
    (upper arm, forearm) to place the wrist at the right spot.
    """
    # J1: base yaw
    j1_rad = math.atan2(y, x) if (abs(x) + abs(y)) > 0.01 else 0.0

    # Work in the arm plane: radial distance from Z axis, height
    target_r = math.sqrt(x * x + y * y)
    target_z = z

    # With pitch234 = 0 the tool extends horizontally, so the wrist is:
    wrist_r = target_r - _TOOL
    wrist_z = target_z

    # 2-link IK from shoulder (0, BASE_HEIGHT) to wrist (wrist_r, wrist_z)
    dr = wrist_r          # horizontal offset from axis
    dz = wrist_z - BASE_HEIGHT   # vertical offset from shoulder

    d = math.sqrt(dr * dr + dz * dz)
    max_reach = UPPER_ARM + FOREARM - 1
    min_reach = abs(UPPER_ARM - FOREARM) + 1
    d = max(min_reach, min(d, max_reach))

    # Elbow angle via law of cosines
    cos_j3 = (d * d - UPPER_ARM * UPPER_ARM - FOREARM * FOREARM) / \
             (2 * UPPER_ARM * FOREARM)
    cos_j3 = max(-1.0, min(1.0, cos_j3))
    j3_rad = -math.acos(cos_j3)  # negative = elbow-down (more natural pose)

    # Shoulder angle
    alpha = math.atan2(dz, dr)
    beta = math.atan2(FOREARM * math.sin(-j3_rad),
                      UPPER_ARM + FOREARM * math.cos(-j3_rad))
    j2_rad = alpha + beta

    # J4: pitch234 = j2 + j3 + j4 = 0  →  j4 = -(j2 + j3)
    j4_rad = -(j2_rad + j3_rad)

    return (math.degrees(j1_rad), math.degrees(j2_rad),
            math.degrees(j3_rad), math.degrees(j4_rad), 0.0)


# ── Predefined test shapes ────────────────────────────────────────────

def _shape_rectangle(t, w=60, h=40, cx=150, cy=0, z=80):
    """Point on a rectangle outline in the XY plane at parameter t ∈ [0,1]."""
    perim = 2 * (w + h)
    d = (t % 1.0) * perim
    if d < w:
        return cx - w / 2 + d, cy - h / 2, z
    d -= w
    if d < h:
        return cx + w / 2, cy - h / 2 + d, z
    d -= h
    if d < w:
        return cx + w / 2 - d, cy + h / 2, z
    d -= w
    return cx - w / 2, cy + h / 2 - d, z


def _shape_circle(t, r=30, cx=150, cy=0, z=80):
    """Point on a circle in the XY plane at parameter t ∈ [0,1]."""
    a = 2 * math.pi * (t % 1.0)
    return cx + r * math.cos(a), cy + r * math.sin(a), z


def _shape_cylinder(t, r=25, h=50, cx=120, cz=70, spirals=8):
    """Point on a cylinder surface via smooth spiral.  t ∈ [0,1]."""
    # Spirals up the cylinder: each full rotation advances one row height
    z = cz + h * (t % 1.0)
    a = 2 * math.pi * spirals * (t % 1.0)
    x = cx + r * math.cos(a)
    y = r * math.sin(a)
    return x, y, z


def _shape_sphere(t, r=30, cx=150, cy=0, cz=80, spirals=8):
    """Point on a sphere surface via smooth spiral.  t ∈ [0,1]."""
    # Spiral from pole to equator (upper hemisphere)
    phi = math.pi / 2 * (t % 1.0)  # 0 (top) → π/2 (equator)
    theta = 2 * math.pi * spirals * (t % 1.0)
    x = cx + r * math.cos(phi) * math.cos(theta)
    y = cy + r * math.cos(phi) * math.sin(theta)
    z = cz + r * math.sin(phi)
    return x, y, z


SHAPES = {
    'rectangle': (_shape_rectangle, 'XY', 5.0),    # (func, trace_plane, duration_sec per loop)
    'circle':    (_shape_circle,    'XY', 5.0),
    'cylinder':  (_shape_cylinder,  None, 10.0),   # None = 3D, not a 2D trace
    'sphere':    (_shape_sphere,    None, 10.0),
}


# ── Simulator connection ──────────────────────────────────────────────

class SimulatorConnection(ArmConnection):
    """Simulated arm connection with three modes.

    Modes (set via ``set_mode``):
      - ``"idle"``  — gentle sine-wave oscillation (default)
      - ``"manual"`` — joints set by ``set_manual_angles``
      - ``"rectangle"`` / ``"circle"`` / ``"cylinder"`` / ``"sphere"``
        — trace a predefined test shape
    """

    _IDLE_OSC = [
        (20.0, 0.08, 0.0),   # J1 — slow gentle sweep
        (15.0, 0.06, 1.0),   # J2
        (10.0, 0.05, 2.0),   # J3
        (8.0,  0.07, 3.0),   # J4
        (5.0,  0.04, 0.5),   # J5
    ]

    def __init__(self):
        self._open = False
        self._t0 = 0.0
        self._lock = threading.Lock()
        self._queue: list[str] = []

        # Mode
        self._mode = 'idle'
        self._manual_angles = [0.0, 0.0, 0.0, 0.0, 0.0]

        # Shape playback
        self._shape_func = None
        self._shape_plane = None
        self._shape_duration = 1.0
        self._shape_t0 = 0.0
        self._shape_speed = 1.0  # loops per duration

        # Point/trace state
        self._point_index = 0
        self._tracing = False
        self._trace_index = 0
        self._trace_plane = "XY"

    # ── ArmConnection interface ───────────────────────────────────────

    def open(self):
        self._open = True
        self._t0 = time.monotonic()
        self._shape_t0 = self._t0
        with self._lock:
            self._queue.append("# Simulator connected")

    def close(self):
        self._open = False
        self._tracing = False

    def is_open(self):
        return self._open

    def write(self, cmd: str):
        cmd = cmd.strip()
        if not cmd:
            return
        c = cmd[0]
        if c == 'p':
            self._sample_point()
        elif c == 't':
            self._toggle_trace()

    def readline(self):
        if not self._open:
            return ""

        time.sleep(0.02)  # ~50 Hz

        with self._lock:
            if self._queue:
                return self._queue.pop(0)

        # Get current joint angles depending on mode
        angles = self._current_angles()
        j1d, j2d, j3d, j4d, j5d = angles

        line = "ANGLES,{:.2f},{:.2f},{:.2f},{:.2f},{:.2f}".format(*angles)

        # If tracing, queue a TRACE line
        if self._tracing:
            tx, ty, tz = _sim_fk(*angles)
            a, b = self._project(tx, ty, tz)
            trace_line = "TRACE,{},{:.4f},{:.4f}".format(self._trace_index, a, b)
            self._trace_index += 1
            with self._lock:
                self._queue.append(trace_line)

        return line

    # ── Mode control (called from UI) ─────────────────────────────────

    def set_mode(self, mode: str):
        """Switch simulator mode.

        Args:
            mode: 'idle', 'manual', 'rectangle', 'circle', 'cylinder', 'sphere'
        """
        self._mode = mode
        if mode in SHAPES:
            func, plane, dur = SHAPES[mode]
            self._shape_func = func
            self._shape_plane = plane
            self._shape_duration = dur
            self._shape_t0 = time.monotonic()
            if plane:
                self._trace_plane = plane
        else:
            self._shape_func = None

    def set_manual_angles(self, angles: list):
        """Set joint angles for manual mode (degrees)."""
        self._manual_angles = list(angles)

    def set_manual_joint(self, joint_index: int, angle_deg: float):
        """Set a single joint angle for manual mode."""
        if 0 <= joint_index < 5:
            self._manual_angles[joint_index] = angle_deg

    def set_speed(self, speed: float):
        """Set playback speed multiplier (1.0 = normal)."""
        self._shape_speed = max(0.1, speed)

    # ── Internal ──────────────────────────────────────────────────────

    def _current_angles(self):
        """Return joint angles (degrees) for current mode."""
        if self._mode == 'manual':
            return list(self._manual_angles)

        if self._mode in SHAPES and self._shape_func:
            t_elapsed = time.monotonic() - self._shape_t0
            t_param = (t_elapsed * self._shape_speed / self._shape_duration) % 1.0
            x, y, z = self._shape_func(t_param)
            return list(_approx_ik(x, y, z))

        # idle mode: gentle oscillation
        t = time.monotonic() - self._t0
        angles = []
        for amp, freq, phase in self._IDLE_OSC:
            angles.append(amp * math.sin(2.0 * math.pi * freq * t + phase))
        return angles

    def _sample_point(self):
        angles = self._current_angles()
        tx, ty, tz = _sim_fk(*angles)
        line = "POINT,{},{:.4f},{:.4f},{:.4f}".format(self._point_index, tx, ty, tz)
        self._point_index += 1
        with self._lock:
            self._queue.append(line)

    def _toggle_trace(self):
        self._tracing = not self._tracing
        if self._tracing:
            self._trace_index = 0
            with self._lock:
                self._queue.append("# TRACE START plane={}".format(self._trace_plane))
        else:
            with self._lock:
                self._queue.append("# TRACE STOP")

    def _project(self, x, y, z):
        if self._trace_plane == "XY":
            return x, y
        elif self._trace_plane == "XZ":
            return x, z
        return y, z
