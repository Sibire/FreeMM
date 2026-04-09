"""Abstract base class for arm connections."""

from abc import ABC, abstractmethod


class ArmConnection(ABC):
    """Interface that all arm data sources must implement.

    Subclasses wrap either a real serial port or the built-in simulator.
    The reader thread calls :meth:`readline` in a loop and dispatches
    the returned protocol lines to the rest of the application.
    """

    @abstractmethod
    def open(self) -> None:
        """Open the connection.  Raises on failure."""

    @abstractmethod
    def close(self) -> None:
        """Close the connection, releasing resources."""

    @abstractmethod
    def readline(self) -> str:
        """Block until a line is available and return it (stripped).

        Returns an empty string on timeout / no data.
        """

    @abstractmethod
    def write(self, cmd: str) -> None:
        """Send a command string to the arm."""

    @abstractmethod
    def is_open(self) -> bool:
        """Return True if the connection is currently open."""
