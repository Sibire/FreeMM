"""Background thread that reads from an ArmConnection and emits Qt signals."""

import math
import time

from PyQt5.QtCore import QThread, pyqtSignal

from diygitizer.connection.base import ArmConnection
from diygitizer.models.arm_state import ArmState
from diygitizer.models.point import Point3D, PointRecord


class ReaderThread(QThread):
    """Continuously reads lines from *connection*, parses the firmware
    protocol, and emits typed Qt signals.

    Signals
    -------
    angles_received(ArmState)
        Emitted for every ``ANGLES,j1,j2,j3,j4,j5`` line.  The ArmState
        has FK already computed.
    point_received(PointRecord)
        Emitted for ``POINT,idx,x,y,z`` lines.
    trace_point_received(tuple)
        Emitted for ``TRACE,idx,a,b`` lines as ``(idx, a, b)``.
    status_received(str)
        Emitted for ``# ...`` status / info lines.
    error_occurred(str)
        Emitted when an exception is caught in the read loop.
    """

    angles_received = pyqtSignal(object)       # ArmState
    point_received = pyqtSignal(object)        # PointRecord
    trace_point_received = pyqtSignal(object)  # (idx, a, b)
    status_received = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, connection: ArmConnection, parent=None):
        super().__init__(parent)
        self._conn = connection
        self._running = False

    def run(self):
        """Main read loop — runs in the background thread."""
        self._running = True
        try:
            while self._running:
                line = self._conn.readline()
                if not line:
                    continue
                self._parse(line)
        except Exception as exc:
            if self._running:
                self.error_occurred.emit(str(exc))

    def stop(self):
        """Signal the read loop to exit."""
        self._running = False

    # ------------------------------------------------------------------
    # Protocol parsing
    # ------------------------------------------------------------------

    def _parse(self, line: str):
        """Dispatch a single protocol line to the appropriate signal."""

        if line.startswith("ANGLES,"):
            self._handle_angles(line)

        elif line.startswith("POINT,"):
            self._handle_point(line)

        elif line.startswith("TRACE,"):
            self._handle_trace(line)

        elif line.startswith("#"):
            # Status / info message from firmware
            msg = line.lstrip("#").strip()
            self.status_received.emit(msg)

    def _handle_angles(self, line: str):
        """Parse ``ANGLES,j1,j2,j3,j4,j5`` (degrees) and emit an ArmState."""
        parts = line.split(",")
        if len(parts) != 6:
            return
        try:
            degs = [float(parts[i]) for i in range(1, 6)]
        except ValueError:
            return

        state = ArmState(
            j1=math.radians(degs[0]),
            j2=math.radians(degs[1]),
            j3=math.radians(degs[2]),
            j4=math.radians(degs[3]),
            j5=math.radians(degs[4]),
        )
        state.compute_fk()
        self.angles_received.emit(state)

    def _handle_point(self, line: str):
        """Parse ``POINT,idx,x,y,z`` and emit a PointRecord."""
        parts = line.split(",")
        if len(parts) != 5:
            return
        try:
            idx = int(parts[1])
            x = float(parts[2])
            y = float(parts[3])
            z = float(parts[4])
        except ValueError:
            return

        record = PointRecord(
            index=idx,
            point=Point3D(x, y, z),
            timestamp=time.time(),
        )
        self.point_received.emit(record)

    def _handle_trace(self, line: str):
        """Parse ``TRACE,idx,a,b`` and emit a tuple."""
        parts = line.split(",")
        if len(parts) != 4:
            return
        try:
            idx = int(parts[1])
            a = float(parts[2])
            b = float(parts[3])
        except ValueError:
            return

        self.trace_point_received.emit((idx, a, b))
