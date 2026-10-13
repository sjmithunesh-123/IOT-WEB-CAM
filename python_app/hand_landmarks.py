"""MediaPipe Tasks hand-landmark adapter."""
from pathlib import Path
from typing import Any

import cv2


class HandLandmarkDetector:
    def __init__(self, model_path: Path, min_detection: float, min_presence: float, min_tracking: float) -> None:
        if not model_path.is_file():
            raise FileNotFoundError(
                f"MediaPipe model missing: {model_path}. Download hand_landmarker.task as documented in README.md."
            )
        import mediapipe as mp
        options = mp.tasks.vision.HandLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=str(model_path)),
            running_mode=mp.tasks.vision.RunningMode.VIDEO,
            num_hands=1,
            min_hand_detection_confidence=min_detection,
            min_hand_presence_confidence=min_presence,
            min_tracking_confidence=min_tracking,
        )
        self._mp = mp
        self._detector = mp.tasks.vision.HandLandmarker.create_from_options(options)
        self._timestamp_ms = 0
        self.last_handedness = "UNKNOWN"

    def detect(self, frame_bgr: Any) -> list[Any]:
        rgb_frame = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        rgb = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=rgb_frame)
        self._timestamp_ms += 33
        result = self._detector.detect_for_video(rgb, self._timestamp_ms)
        if result.handedness and result.handedness[0]:
            self.last_handedness = result.handedness[0][0].category_name.upper()
        else:
            self.last_handedness = "UNKNOWN"
        return result.hand_landmarks[0] if result.hand_landmarks else []

    def close(self) -> None:
        self._detector.close()
