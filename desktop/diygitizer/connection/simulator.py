"""Built-in simulator connection — no hardware required.

The simulator maintains five virtual joint angles that smoothly oscillate
at different frequencies, producing realistic-looking arm motion.  It
speaks the same line-based protocol as the real firmware so the rest of
the application does not need to know the difference.
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


def _sim_fk(j1d, j2d, j3d, j4d, j5d):
    """Lightweight FK using only the math module (mirrors firmware)."""
    j1 = math.radians(j1d)
    j2 = math.radians(j2d)
    j3 = math.radians(j3d)
    j4 = math.radians(j4d)
    j5 = math.radians(j5d)

    c1 = math.cos(j1)
    s1 = math.sin(j1)

    elbow_x = UPPER_ARM * math.cos(j2) * c1
    elbow_y = UPPER_ARM * math.cos(j2) * s1
    elbow_z = BASE_HEIGHT + UPPER_ARM * math.sin(j2)

    pitch23 = j2 + j3
    wrist_x = elbow_x + FOREARM * math.cos(pitch23) * c1
    wrist_y = elbow_y + FOREARM * math.cos(pitch23) * s1
    wrist_z = elbow_z + FOREARM * math.sin(pitch23)

    pitch234 = pitch23 + j4
    cp234 = math.cos(pitch234)
    sp234 = math.sin(pitch234)
    j5x = wrist_x + WRIST_LINK * cp234 * c1
    j5y = wrist_y + WRIST_LINK * cp234 * s1
    j5z = wrist_z + WRIST_LINK * sp234

    fwd_x = cp234 * c1
    fwd_y = cp234 * s1
    fwd_z = sp234

    lat_x = -s1
    lat_y = c1
    lat_z = 0.0

    c5 = math.cos(j5)
    s5 = math.sin(j5)

    pd_x = c5 * fwd_x + s5 * lat_x
    pd_y = c5 * fwd_y + s5 * lat_y
    pd_z = c5 * fwd_z + s5 * lat_z

    tip_x = j5x + PROBE_LEN * pd_x
    tip_y = j5y + PROBE_LEN * pd_y
    tip_z = j5z + PROBE_LEN * pd_z

    return tip_x, tip_y, tip_z


class SimulatorConnection(ArmConnection):
    """Simulated arm connection that oscillates joints automatically.

    The simulator produces ``ANGLES,j1,j2,j3,j4,j5`` lines at ~50 Hz.
    It responds to single-character commands:
        ``p`` — sample a point (next readline returns a ``POINT`` line)
        ``t`` — toggle trace mode (intersperse ``TRACE`` lines with angles)
    """

    # Oscillation parameters: (amplitude_deg, frequency_hz, phase_offset)
    _OSCILLATION = [
        (45.0, 0.13, 0.0),    # J1 — slow base sweep
        (30.0, 0.17, 1.0),    # J2 — shoulder
        (25.0, 0.23, 2.0),    # J3 — elbow
        (20.0, 0.31, 3.0),    # J4 — wrist pitch
        (15.0, 0.11, 0.5),    # J5 — wrist roll
    ]

    def __init__(self):
        self._open = False
        self._t0 = 0.0

        # Pending lines queue (thread-safe via lock)
        self._lock = threading.Lock()
        self._queue: list[str] = []

        # Point sampling state
        self._point_index = 0

        # Trace state
        self._tracing = False
        self._trace_index = 0
        self._trace_plane = "XY"

    # ------------------------------------------------------------------
    # ArmConnection interface
    # ------------------------------------------------------------------

    def open(self) -> None:
        self._open = True
        self._t0 = time.monotonic()
        with self._lock:
            self._queue.append("# Simulator connected")

    def close(self) -> None:
        self._open = False
        self._tracing = False

    def is_open(self) -> bool:
        return self._open

    def write(self, cmd: str) -> None:
        """Handle single-character commands, mirroring firmware protocol."""
        cmd = cmd.strip()
        if not cmd:
            return

        c = cmd[0]
        if c == "p":
            self._sample_point()
        elif c == "t":
            self._toggle_trace()

    def readline(self) -> str:
        """Return the next protocol line at ~50 Hz.

        If there are pending command-response lines they are returned
        first.  Otherwise an ``ANGLES`` line is generated from the
        current simulated joint state.  When tracing is active, a
        ``TRACE`` line is emitted alongside each ``ANGLES`` line.
        """
        if not self._open:
            return ""

        # ~50 Hz pacing
        time.sleep(0.02)

        # Return any pending lines first (point samples, status messages)
        with self._lock:
            if self._queue:
                return self._queue.pop(0)

        # Compute oscillating joint angles
        t = time.monotonic() - self._t0
        angles = []
        for amp, freq, phase in self._OSCILLATION:
            angles.append(amp * math.sin(2.0 * math.pi * freq * t + phase))

        j1d, j2d, j3d, j4d, j5d = angles

        # Build ANGLES line (degrees, 2 decimal places)
        line = "ANGLES,{:.2f},{:.2f},{:.2f},{:.2f},{:.2f}".format(
            j1d, j2d, j3d, j4d, j5d
        )

        # If tracing, also queue a TRACE line for the next read
        if self._tracing:
            tx, ty, tz = _sim_fk(j1d, j2d, j3d, j4d, j5d)
            a, b = self._project(tx, ty, tz)
            trace_line = "TRACE,{},{:.4f},{:.4f}".format(self._trace_index, a, b)
            self._trace_index += 1
            with self._lock:
                self._queue.append(trace_line)

        return line

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _current_angles(self):
        """Return the current simulated joint angles in degrees."""
        t = time.monotonic() - self._t0
        angles = []
        for amp, freq, phase in self._OSCILLATION:
            angles.append(amp * math.sin(2.0 * math.pi * freq * t + phase))
        return angles

    def _sample_point(self):
        """Compute a POINT line and queue it."""
        angles = self._current_angles()
        tx, ty, tz = _sim_fk(*angles)
        line = "POINT,{},{:.4f},{:.4f},{:.4f}".format(
            self._point_index, tx, ty, tz
        )
        self._point_index += 1
        with self._lock:
            self._queue.append(line)

    def _toggle_trace(self):
        """Toggle trace recording on/off."""
        self._tracing = not self._tracing
        if self._tracing:
            self._trace_index = 0
            with self._lock:
                self._queue.append("# TRACE START plane={}".format(self._trace_plane))
        else:
            with self._lock:
                self._queue.append("# TRACE STOP")

    def _project(self, x, y, z):
        """Project XYZ onto the current trace plane → (a, b)."""
        if self._trace_plane == "XY":
            return x, y
        elif self._trace_plane == "XZ":
            return x, z
        else:  # YZ
            return y, z
