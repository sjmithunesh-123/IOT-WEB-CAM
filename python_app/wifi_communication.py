"""HTTP transport for sending stable gestures to the ESP32 over Wi-Fi."""
import json
import logging
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from config import VALID_COMMANDS
from protocol import normalize_command

logger = logging.getLogger(__name__)


@dataclass
class WifiStatus:
    connected: bool = False
    last_response: str = ""
    last_error: str = ""


class Esp32Wifi:
    """Send one JSON gesture command per accepted gesture transition."""

    def __init__(self, host: str, port: int = 80, timeout: float = 1.0) -> None:
        self.host = host.strip()
        self.port = port
        self.timeout = timeout
        self.status = WifiStatus()

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    def _request(self, method: str, path: str, body: bytes | None = None) -> tuple[int, str]:
        headers = {"Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        request = Request(f"{self.base_url}{path}", data=body, headers=headers, method=method)
        with urlopen(request, timeout=self.timeout) as response:
            return response.getcode(), response.read().decode("utf-8", errors="replace")

    def connect(self) -> bool:
        if not self.host:
            self.status = WifiStatus(last_error="No ESP32 Wi-Fi IP configured")
            return False
        try:
            code, body = self._request("GET", "/health")
            self.status = WifiStatus(connected=200 <= code < 300, last_response=body)
            if not self.status.connected:
                self.status.last_error = f"ESP32 health returned HTTP {code}"
            return self.status.connected
        except (OSError, HTTPError, URLError, ValueError) as exc:
            self.status = WifiStatus(last_error=str(exc))
            logger.warning("Unable to reach ESP32 at %s: %s", self.base_url, exc)
            return False

    def send(self, command: str, pattern: str | None = None) -> bool:
        normalized = normalize_command(command)
        if normalized not in VALID_COMMANDS:
            self.status.last_error = f"Unsupported command: {command!r}"
            return False
        if pattern is not None and (len(pattern) != 5 or any(bit not in "01" for bit in pattern)):
            self.status.last_error = f"Invalid finger pattern: {pattern!r}"
            return False
        if not self.host:
            self.status.connected = False
            self.status.last_error = "No ESP32 Wi-Fi IP configured"
            return False
        payload = {"gesture": normalized}
        if pattern is not None:
            payload["pattern"] = pattern
        body = json.dumps(payload).encode("utf-8")
        try:
            code, response_body = self._request("POST", "/gesture", body)
            self.status.last_response = response_body
            self.status.connected = 200 <= code < 300
            logger.info("Wi-Fi gesture %s pattern=%s destination=%s HTTP %d", normalized, pattern or "-", self.base_url, code)
            if not self.status.connected:
                self.status.last_error = f"ESP32 gesture endpoint returned HTTP {code}"
            return self.status.connected
        except (OSError, HTTPError, URLError, ValueError) as exc:
            self.status.connected = False
            self.status.last_error = str(exc)
            logger.warning("Wi-Fi gesture %s pattern=%s destination=%s failed: %s", normalized, pattern or "-", self.base_url, exc)
            return False

    def close(self) -> None:
        self.status.connected = False
