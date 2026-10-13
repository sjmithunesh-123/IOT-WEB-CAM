"""Rule-based demo gesture recognition and temporal stabilization."""
from collections import Counter, deque
from dataclasses import dataclass
from typing import Any, Sequence

from config import FINGER_EXTENSION_RATIO


# MediaPipe landmark indices used by the simple demonstration rules.
WRIST = 0
THUMB_CMC, THUMB_MCP, THUMB_IP, THUMB_TIP = 1, 2, 3, 4
INDEX_MCP, INDEX_PIP, INDEX_DIP, INDEX_TIP = 5, 6, 7, 8
MIDDLE_MCP, MIDDLE_PIP, MIDDLE_DIP, MIDDLE_TIP = 9, 10, 11, 12
RING_MCP, RING_PIP, RING_DIP, RING_TIP = 13, 14, 15, 16
PINKY_MCP, PINKY_PIP, PINKY_DIP, PINKY_TIP = 17, 18, 19, 20

Point = Any
FingerStates = tuple[bool, bool, bool, bool, bool]

GESTURE_BY_PATTERN = {
    "01111": "HELLO",
    "10111": "HELP ME",
    "11011": "THANK YOU",
    "11101": "WELCOME",
    "11110": "YES",
    "11111": "HI",
}


@dataclass(frozen=True)
class GestureResult:
    label: str
    hand_detected: bool
    reason: str = ""
    finger_states: FingerStates = (False, False, False, False, False)
    handedness: str = "UNKNOWN"


def _coordinates(point: Point) -> tuple[float, float, float]:
    """Read either MediaPipe NormalizedLandmark objects or test sequences."""
    if hasattr(point, "x") and hasattr(point, "y"):
        return float(point.x), float(point.y), float(getattr(point, "z", 0.0))
    return float(point[0]), float(point[1]), float(point[2] if len(point) > 2 else 0.0)


def _distance(first: Point, second: Point) -> float:
    first_coordinates = _coordinates(first)
    second_coordinates = _coordinates(second)
    return sum((a - b) ** 2 for a, b in zip(first_coordinates, second_coordinates)) ** 0.5


def _is_extended(landmarks: Sequence[Point], tip: int, pip: int) -> bool:
    """Estimate extension using distances normalized by the hand's palm geometry."""
    wrist_to_pip = _distance(landmarks[pip], landmarks[WRIST])
    wrist_to_tip = _distance(landmarks[tip], landmarks[WRIST])
    if wrist_to_pip < 1e-6:
        return False
    return wrist_to_tip > wrist_to_pip * FINGER_EXTENSION_RATIO


def _is_thumb_extended(landmarks: Sequence[Point]) -> bool:
    """Detect thumb spread relative to the index MCP, not image left/right."""
    tip_to_index_mcp = _distance(landmarks[THUMB_TIP], landmarks[INDEX_MCP])
    ip_to_index_mcp = _distance(landmarks[THUMB_IP], landmarks[INDEX_MCP])
    if ip_to_index_mcp < 1e-6:
        return False
    return tip_to_index_mcp > ip_to_index_mcp * FINGER_EXTENSION_RATIO


def get_finger_states(landmarks: Sequence[Point]) -> FingerStates:
    """Return extended states in thumb, index, middle, ring, pinky order."""
    return (
        _is_thumb_extended(landmarks),
        _is_extended(landmarks, INDEX_TIP, INDEX_PIP),
        _is_extended(landmarks, MIDDLE_TIP, MIDDLE_PIP),
        _is_extended(landmarks, RING_TIP, RING_PIP),
        _is_extended(landmarks, PINKY_TIP, PINKY_PIP),
    )


def finger_pattern(states: FingerStates) -> str:
    """Encode states as T I M R P bits, where 1 means extended."""
    return "".join("1" if state else "0" for state in states)


def classify_landmarks(landmarks: Sequence[Point] | None, handedness: str | None = None) -> GestureResult:
    """Classify the exact supported T I M R P binary gesture mappings."""
    side = (handedness or "UNKNOWN").upper()
    if not landmarks:
        return GestureResult("NO HAND", False, "No hand landmarks", handedness=side)
    if len(landmarks) < 21:
        return GestureResult("UNKNOWN", True, "Incomplete landmark set", handedness=side)

    states = get_finger_states(landmarks)
    pattern = finger_pattern(states)
    label = GESTURE_BY_PATTERN.get(pattern, "UNKNOWN")
    reason = f"Pattern {pattern}: {label}" if label != "UNKNOWN" else f"Unsupported finger pattern: {pattern}"
    return GestureResult(label, True, reason, states, side)


class GestureStabilizer:
    """Require repeated labels and suppress held-gesture duplicates."""

    def __init__(self, window_size: int = 5) -> None:
        if window_size < 1:
            raise ValueError("window_size must be positive")
        self._labels: deque[str] = deque(maxlen=window_size)
        self._stable_label = "NO HAND"
        self._armed = True

    @property
    def stable_label(self) -> str:
        return self._stable_label

    def update(self, label: str) -> tuple[str, bool]:
        """Return (stable label, should_send). Sending occurs on transitions only."""
        self._labels.append(label)
        if len(self._labels) < self._labels.maxlen:
            return self._stable_label, False
        candidate, count = Counter(self._labels).most_common(1)[0]
        if count < len(self._labels):
            return self._stable_label, False
        if candidate == "NO HAND":
            changed = self._stable_label != "NO HAND"
            self._stable_label = "NO HAND"
            self._armed = True
            return self._stable_label, changed
        if candidate != self._stable_label:
            self._stable_label = candidate
            should_send = self._armed or candidate != "NO HAND"
            self._armed = False
            return self._stable_label, should_send
        return self._stable_label, False
