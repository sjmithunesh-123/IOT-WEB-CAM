"""Application configuration for the webcam-to-ESP32 demonstrator."""
from dataclasses import dataclass
from pathlib import Path
import os


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = PROJECT_ROOT / "assets" / "models" / "hand_landmarker.task"


@dataclass(frozen=True)
class AppConfig:
    transport: str = os.getenv("SMART_GLOVE_TRANSPORT", "wifi").lower()
    camera_index: int = int(os.getenv("SMART_GLOVE_CAMERA_INDEX", "0"))
    serial_port: str = os.getenv("SMART_GLOVE_SERIAL_PORT", "")
    serial_baudrate: int = int(os.getenv("SMART_GLOVE_SERIAL_BAUD", "115200"))
    esp32_ip: str = os.getenv("SMART_GLOVE_ESP32_IP", "192.168.1.100")
    esp32_http_port: int = int(os.getenv("SMART_GLOVE_ESP32_HTTP_PORT", "80"))
    http_timeout: float = float(os.getenv("SMART_GLOVE_HTTP_TIMEOUT", "1.0"))
    model_path: Path = MODEL_PATH
    stability_window: int = int(os.getenv("SMART_GLOVE_STABILITY_WINDOW", "5"))
    min_detection_confidence: float = float(os.getenv("SMART_GLOVE_MIN_DETECTION", "0.6"))
    min_presence_confidence: float = float(os.getenv("SMART_GLOVE_MIN_PRESENCE", "0.6"))
    min_tracking_confidence: float = float(os.getenv("SMART_GLOVE_MIN_TRACKING", "0.6"))
    camera_width: int = 960
    camera_height: int = 540


SUPPORTED_GESTURES = ("HELLO", "HELP ME", "THANK YOU", "WELCOME", "YES", "HI", "UNKNOWN")
NON_AUDIO_COMMANDS = ("NO HAND",)
VALID_COMMANDS = SUPPORTED_GESTURES + NON_AUDIO_COMMANDS
AUDIO_TRACKS = {
    "HELLO": 1,
    "HELP ME": 2,
    "THANK YOU": 3,
    "WELCOME": 4,
    "YES": 5,
    "HI": 6,
}

FINGER_EXTENSION_RATIO = float(os.getenv("SMART_GLOVE_FINGER_RATIO", "1.08"))

# Interior joint angles in degrees: straight at/above the first value, bent
# at/below the second. The gap prevents boundary flicker (hysteresis).
FINGER_ANGLE_THRESHOLDS = {
    "THUMB": (155.0, 140.0),
    "INDEX": (155.0, 140.0),
    "MIDDLE": (155.0, 140.0),
    "RING": (155.0, 140.0),
    "LITTLE": (155.0, 140.0),
}
for _finger in FINGER_ANGLE_THRESHOLDS:
    _key = f"SMART_GLOVE_{_finger}_STRAIGHT_ANGLE"
    _bent_key = f"SMART_GLOVE_{_finger}_BENT_ANGLE"
    _straight, _bent = FINGER_ANGLE_THRESHOLDS[_finger]
    FINGER_ANGLE_THRESHOLDS[_finger] = (
        float(os.getenv(_key, str(_straight))),
        float(os.getenv(_bent_key, str(_bent))),
    )
