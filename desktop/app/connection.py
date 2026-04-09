"""Data source abstraction: real serial + built-in simulator.

Both SerialSource and SimulatorSource emit the same signals,
so the rest of the app doesn't know or care which is active.
"""

import time
import serial
import serial.tools.list_ports
from PyQt5.QtCore import QObject, QThread, QTimer, pyqtSignal
from app.kinematics import forward_kinematics, JOINT_LIMITS


def list_serial_ports():
    """Return list of available serial port names."""
    return [p.device for p in serial.tools.list_ports.comports()]


class DataSource(QObject):
    """Abstract base for arm data sources."""

    angles_updated = pyqtSignal(list)                    # [j1..j5] degrees
    position_updated = pyqtSignal(object, object)        # tip_xyz, joint_positions_dict
    point_sampled = pyqtSignal(int, float, float, float) # idx, x, y, z
    trace_point = pyqtSignal(int, float, float)          # idx, a, b
    trace_started = pyqtSignal(str)                      # plane name
    trace_stopped = pyqtSignal()
    status_message = pyqtSignal(str)
    connected = pyqtSignal()
    disconnected = pyqtSignal()

    def send_command(self, cmd):
        raise NotImplementedError

    def start(self):
        raise NotImplementedError

    def stop(self):
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Real serial connection to ESP32
# ---------------------------------------------------------------------------

class SerialReader(QThread):
    """Background thread that reads lines from serial port."""

    line_received = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, port, baud=115200):
        super().__init__()
        self.port = port
        self.baud = baud
        self._running = False
        self._serial = None

    def run(self):
        try:
            self._serial = serial.Serial(self.port, self.baud, timeout=0.1)
            self._running = True
            while self._running:
                if self._serial.in_waiting:
                    line = self._serial.readline().decode('utf-8', errors='replace').strip()
                    if line:
                        self.line_received.emit(line)
                else:
                    self.msleep(5)
        except serial.SerialException as e:
            self.error.emit(str(e))
        finally:
            if self._serial and self._serial.is_open:
                self._serial.close()

    def stop(self):
        self._running = False

    def write(self, data):
        if self._serial and self._serial.is_open:
            self._serial.write((data + '\n').encode('utf-8'))


class SerialSource(DataSource):
    """Connects to real ESP32 over serial."""

    def __init__(self, port, baud=115200):
        super().__init__()
        self.port = port
        self.baud = baud
        self._reader = None

    def start(self):
        self._reader = SerialReader(self.port, self.baud)
        self._reader.line_received.connect(self._parse_line)
        self._reader.error.connect(lambda e: self.status_message.emit(f"Serial error: {e}"))
        self._reader.error.connect(lambda _: self.disconnected.emit())
        self._reader.start()
        self.connected.emit()
        self.status_message.emit(f"Connected to {self.port}")

    def stop(self):
        if self._reader:
            self._reader.stop()
            self._reader.wait(2000)
            self._reader = None
        self.disconnected.emit()

    def send_command(self, cmd):
        if self._reader:
            self._reader.write(cmd)

    def _parse_line(self, line):
        """Parse firmware serial protocol lines."""
        if line.startswith("ANGLES,"):
            parts = line.split(",")
            if len(parts) == 6:
                try:
                    angles = [float(parts[i]) for i in range(1, 6)]
                    self.angles_updated.emit(angles)
                    fk = forward_kinematics(angles)
                    self.position_updated.emit(fk['tip'], fk)
                except ValueError:
                    pass

        elif line.startswith("POINT,"):
            parts = line.split(",")
            if len(parts) == 5:
                try:
                    idx = int(parts[1])
                    x, y, z = float(parts[2]), float(parts[3]), float(parts[4])
                    self.point_sampled.emit(idx, x, y, z)
                except ValueError:
                    pass

        elif line.startswith("TRACE,"):
            parts = line.split(",")
            if len(parts) == 4:
                try:
                    idx = int(parts[1])
                    a, b = float(parts[2]), float(parts[3])
                    self.trace_point.emit(idx, a, b)
                except ValueError:
                    pass

        elif line.startswith("# TRACE START"):
            plane = line.split("plane=")[-1] if "plane=" in line else "XZ"
            self.trace_started.emit(plane)

        elif line.startswith("# TRACE STOP"):
            self.trace_stopped.emit()

        elif line.startswith("#"):
            self.status_message.emit(line[2:].strip())


# ---------------------------------------------------------------------------
# Built-in simulator (no hardware needed)
# ---------------------------------------------------------------------------

class SimulatorSource(DataSource):
    """Simulated arm driven by virtual joint sliders.

    Runs FK in Python and emits the same signals as SerialSource.
    """

    def __init__(self):
        super().__init__()
        self.joint_angles = [0.0] * 5
        self._timer = None
        self._point_index = 0
        self._trace_index = 0
        self._tracing = False
        self._trace_plane = 1  # XZ

    def start(self):
        self._timer = QTimer()
        self._timer.timeout.connect(self._tick)
        self._timer.start(20)  # 50Hz
        self.connected.emit()
        self.status_message.emit("Simulator active")

    def stop(self):
        if self._timer:
            self._timer.stop()
            self._timer = None
        self.disconnected.emit()

    def send_command(self, cmd):
        """Handle commands the same way firmware would."""
        cmd = cmd.strip()
        if not cmd:
            return

        c = cmd[0]
        if c == 'p':
            self._sample_point()
        elif c == 't':
            self._toggle_trace()
        elif c == '1':
            self._trace_plane = 0
            self.status_message.emit("Plane: XY")
        elif c == '2':
            self._trace_plane = 1
            self.status_message.emit("Plane: XZ")
        elif c == '3':
            self._trace_plane = 2
            self.status_message.emit("Plane: YZ")
        elif c == 'r':
            self._point_index = 0
            self._trace_index = 0
            self.status_message.emit("Reset")

    def set_joint(self, joint_index, angle_deg):
        """Set a single joint angle (called by UI sliders)."""
        lo, hi = JOINT_LIMITS[joint_index]
        self.joint_angles[joint_index] = max(lo, min(hi, angle_deg))

    def _tick(self):
        """Periodic update — compute FK and emit signals."""
        fk = forward_kinematics(self.joint_angles)
        self.angles_updated.emit(list(self.joint_angles))
        self.position_updated.emit(fk['tip'], fk)

        if self._tracing:
            tip = fk['tip']
            a, b = self._get_trace_coords(tip)
            self.trace_point.emit(self._trace_index, a, b)
            self._trace_index += 1

    def _sample_point(self):
        fk = forward_kinematics(self.joint_angles)
        tip = fk['tip']
        self.point_sampled.emit(self._point_index, float(tip[0]), float(tip[1]), float(tip[2]))
        self._point_index += 1

    def _toggle_trace(self):
        self._tracing = not self._tracing
        if self._tracing:
            self._trace_index = 0
            plane_names = ["XY", "XZ", "YZ"]
            self.trace_started.emit(plane_names[self._trace_plane])
        else:
            self.trace_stopped.emit()

    def _get_trace_coords(self, tip):
        if self._trace_plane == 0:
            return float(tip[0]), float(tip[1])
        elif self._trace_plane == 1:
            return float(tip[0]), float(tip[2])
        else:
            return float(tip[1]), float(tip[2])
