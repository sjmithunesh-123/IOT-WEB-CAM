import sys
from pathlib import Path
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1]))

import webcam


class ClosedCamera:
    def __init__(self):
        self.released = False

    def isOpened(self):
        return False

    def release(self):
        self.released = True


class WebcamCleanupTests(unittest.TestCase):
    def test_camera_is_released_when_initialization_fails(self):
        camera = ClosedCamera()
        config = type("Config", (), {"camera_index": 0})()

        with patch.object(webcam.cv2, "VideoCapture", return_value=camera), patch.object(webcam.cv2, "destroyAllWindows") as destroy_windows:
            with self.assertRaises(RuntimeError):
                webcam.run_camera(config, None, None, None)

        self.assertTrue(camera.released)
        destroy_windows.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
