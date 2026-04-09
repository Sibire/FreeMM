"""Real serial connection to the ESP32 via pyserial."""

import serial
import serial.tools.list_ports

from diygitizer.config import BAUD_RATE
from diygitizer.connection.base import ArmConnection


def list_serial_ports():
    """Return a list of available serial port device names."""
    return [p.device for p in serial.tools.list_ports.comports()]


class SerialConnection(ArmConnection):
    """Wraps a pyserial ``Serial`` object.

    Parameters
    ----------
    port : str
        System device name, e.g. ``"COM3"`` or ``"/dev/ttyUSB0"``.
    baudrate : int
        Baud rate (default from config).
    """

    def __init__(self, port: str, baudrate: int = BAUD_RATE):
        self._port = port
        self._baudrate = baudrate
        self._serial: serial.Serial | None = None

    # ------------------------------------------------------------------
    # ArmConnection interface
    # ------------------------------------------------------------------

    def open(self) -> None:
        """Open the serial port.  Raises ``serial.SerialException`` on failure."""
        self._serial = serial.Serial(
            port=self._port,
            baudrate=self._baudrate,
            timeout=0.1,  # 100 ms read timeout
        )

    def close(self) -> None:
        """Close the serial port if it is open."""
        if self._serial is not None:
            try:
                if self._serial.is_open:
                    self._serial.close()
            except Exception:
                pass
            finally:
                self._serial = None

    def readline(self) -> str:
        """Read one line from the serial port (blocking up to timeout).

        Returns an empty string when there is nothing to read or the
        port has been closed / disconnected.
        """
        if self._serial is None or not self._serial.is_open:
            return ""
        try:
            raw = self._serial.readline()
            if raw:
                return raw.decode("utf-8", errors="replace").strip()
            return ""
        except serial.SerialException:
            # Port was unplugged or similar
            self.close()
            return ""
        except OSError:
            self.close()
            return ""

    def write(self, cmd: str) -> None:
        """Send a command to the arm.

        A newline is appended automatically.
        """
        if self._serial is not None and self._serial.is_open:
            try:
                self._serial.write((cmd + "\n").encode("utf-8"))
            except (serial.SerialException, OSError):
                self.close()

    def is_open(self) -> bool:
        """Return True if the underlying serial port is open."""
        return self._serial is not None and self._serial.is_open
