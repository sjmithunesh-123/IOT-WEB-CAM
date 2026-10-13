"""Reliable newline-delimited USB serial communication with the ESP32."""
from dataclasses import dataclass
import logging
from typing import Protocol

from protocol import encode_command

logger = logging.getLogger(__name__)


class SerialLike(Protocol):
    is_open: bool
    def write(self, data: bytes) -> int: ...
    def readline(self) -> bytes: ...
    def close(self) -> None: ...


@dataclass
class SerialStatus:
    connected: bool = False
    last_response: str = ""
    last_error: str = ""


class Esp32Serial:
    def __init__(self, port: str, baudrate: int = 115200, timeout: float = 0.2) -> None:
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self._serial: SerialLike | None = None
        self.status = SerialStatus()

    @staticmethod
    def list_ports() -> list[str]:
        try:
            from serial.tools import list_ports
            return [item.device for item in list_ports.comports()]
        except ImportError:
            return []

    def connect(self) -> bool:
        if not self.port:
            self.status.last_error = "No serial port configured"
            return False
        try:
            import serial
            self._serial = serial.Serial(self.port, self.baudrate, timeout=self.timeout)
            self.status = SerialStatus(connected=True)
            return True
        except (OSError, serial.SerialException) as exc:
            self.status = SerialStatus(last_error=str(exc))
            logger.error("Unable to open ESP32 serial port %s: %s", self.port, exc)
            return False

    def send(self, command: str, pattern: str | None = None) -> bool:
        if self._serial is None or not self.status.connected:
            self.status.last_error = "Serial port is not connected"
            return False
        try:
            self._serial.write(encode_command(command))
            response = self._serial.readline().decode("ascii", errors="replace").strip()
            self.status.last_response = response
            return True
        except (OSError, ValueError) as exc:
            self.status.connected = False
            self.status.last_error = str(exc)
            logger.error("Serial communication failed: %s", exc)
            return False

    def close(self) -> None:
        if self._serial is not None:
            self._serial.close()
        self._serial = None
        self.status.connected = False
