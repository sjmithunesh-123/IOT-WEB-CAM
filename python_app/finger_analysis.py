"""Per-finger flex diagnostics from MediaPipe normalized landmarks.

The displayed measurement is the interior angle at the main bending joint in
degrees (180 degrees is straight; decreasing angles indicate more bending).
These are image-space landmark angles, not clinical measurements.
"""
from collections import deque
from math import acos, degrees, sqrt
from typing import Any, Sequence

FINGER_JOINTS = {
    # (proximal landmark, bending joint, distal landmark)
    "THUMB": (2, 3, 4),       # IP angle
    "INDEX": (5, 6, 7),       # PIP angle
    "MIDDLE": (9, 10, 11),
    "RING": (13, 14, 15),
    "LITTLE": (17, 18, 19),
}


def _xyz(point: Any) -> tuple[float, float, float]:
    if hasattr(point, "x") and hasattr(point, "y"):
        return float(point.x), float(point.y), float(getattr(point, "z", 0.0))
    return float(point[0]), float(point[1]), float(point[2] if len(point) > 2 else 0.0)


def joint_angle_degrees(a: Any, joint: Any, c: Any) -> float:
    """Return the 0..180 interior angle at *joint* using normalized x/y/z."""
    p, q, r = _xyz(a), _xyz(joint), _xyz(c)
    u = tuple(x - y for x, y in zip(p, q))
    v = tuple(x - y for x, y in zip(r, q))
    nu = sqrt(sum(x * x for x in u))
    nv = sqrt(sum(x * x for x in v))
    if nu < 1e-9 or nv < 1e-9:
        return 0.0
    cosine = max(-1.0, min(1.0, sum(x * y for x, y in zip(u, v)) / (nu * nv)))
    return degrees(acos(cosine))


def measure_fingers(landmarks: Sequence[Any]) -> dict[str, float]:
    """Return the five independent major-joint angles, in degrees."""
    if len(landmarks) < 21:
        raise ValueError("Expected all 21 MediaPipe hand landmarks")
    return {name: joint_angle_degrees(*(landmarks[i] for i in joints))
            for name, joints in FINGER_JOINTS.items()}


class FingerStateSmoother:
    """Per-finger hysteresis plus a short majority vote for stable display."""
    def __init__(self, thresholds: dict[str, tuple[float, float]], window_size: int = 3) -> None:
        if window_size < 1:
            raise ValueError("window_size must be positive")
        missing = set(FINGER_JOINTS) - set(thresholds)
        if missing:
            raise ValueError(f"Missing thresholds for: {', '.join(sorted(missing))}")
        for name in FINGER_JOINTS:
            straight_at, bent_at = thresholds[name]
            if not 0.0 <= bent_at <= straight_at <= 180.0:
                raise ValueError(f"Invalid angle thresholds for {name}: {thresholds[name]}")
        self.thresholds = thresholds
        self._history = {name: deque(maxlen=window_size) for name in FINGER_JOINTS}
        self._states: dict[str, str | None] = {name: None for name in FINGER_JOINTS}

    def update(self, measurements: dict[str, float]) -> dict[str, str]:
        states = {}
        for name in FINGER_JOINTS:
            value = measurements[name]
            straight_at, bent_at = self.thresholds[name]
            state = self._states[name]
            if state is None:
                raw = "STRAIGHT" if value >= straight_at else "BENT"
            elif state == "STRAIGHT":
                raw = "BENT" if value <= bent_at else "STRAIGHT"
            else:
                raw = "STRAIGHT" if value >= straight_at else "BENT"
            history = self._history[name]
            history.append(raw)
            # Do not delay clear transitions by a whole window; vote only when
            # at least two observations agree, while retaining hysteresis.
            chosen = max(set(history), key=history.count)
            if history.count(chosen) > len(history) // 2:
                self._states[name] = chosen
            states[name] = self._states[name] or raw
        return states

    def reset(self) -> None:
        for name in FINGER_JOINTS:
            self._history[name].clear()
            self._states[name] = None
