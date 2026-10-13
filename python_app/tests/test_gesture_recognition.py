import sys
from pathlib import Path
import unittest
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parents[1]))

from gesture_recognition import GestureStabilizer, classify_landmarks, finger_pattern


def pose(extended):
    points = [[0.0, 0.5, 0.0] for _ in range(21)]
    for tip, pip in ((8, 6), (12, 10), (16, 14), (20, 18)):
        if extended[(tip - 8) // 4 + 1]:
            points[tip][1] = 0.1
            points[pip][1] = 0.3
        else:
            points[tip][1] = 0.45
            points[pip][1] = 0.3
    points[4][0] = 0.3 if extended[0] else 0.05
    points[3][0] = 0.1 if extended[0] else 0.15
    points[2][0] = 0.08 if extended[0] else 0.12
    return points


class GestureTests(unittest.TestCase):
    def test_no_hand(self):
        self.assertEqual(classify_landmarks(None).label, "NO HAND")

    def test_exact_binary_mappings(self):
        expected = {
            (False, True, True, True, True): ("01111", "HELLO"),
            (True, False, True, True, True): ("10111", "HELP ME"),
            (True, True, False, True, True): ("11011", "THANK YOU"),
            (True, True, True, False, True): ("11101", "WELCOME"),
            (True, True, True, True, False): ("11110", "YES"),
            (True, True, True, True, True): ("11111", "HI"),
        }
        for states, (pattern, label) in expected.items():
            with self.subTest(states=states):
                result = classify_landmarks(pose(states))
                self.assertEqual(finger_pattern(result.finger_states), pattern)
                self.assertEqual(result.label, label)

    def test_mediapipe_landmark_objects_are_supported(self):
        landmarks = [SimpleNamespace(x=point[0], y=point[1], z=point[2]) for point in pose((True, True, True, True, True))]
        self.assertEqual(classify_landmarks(landmarks).label, "HI")

    def test_supported_demo_poses(self):
        self.assertEqual(classify_landmarks(pose((False, False, False, False, False)), "LEFT").label, "UNKNOWN")

    def test_left_and_right_hands_use_same_pose_rules(self):
        landmarks = pose((True, True, True, True, True))
        self.assertEqual(classify_landmarks(landmarks, "LEFT").label, "HI")
        self.assertEqual(classify_landmarks(landmarks, "RIGHT").label, "HI")

    def test_unsupported_pose_is_unknown(self):
        result = classify_landmarks(pose((False, False, False, False, False)))
        self.assertEqual(result.label, "UNKNOWN")
        self.assertIn("00000", result.reason)

    def test_stable_transition_sends_once_and_rearms(self):
        stabilizer = GestureStabilizer(3)
        self.assertFalse(any(stabilizer.update("HI")[1] for _ in range(2)))
        self.assertTrue(stabilizer.update("HI")[1])
        self.assertFalse(stabilizer.update("HI")[1])
        for _ in range(3):
            stabilizer.update("NO HAND")
        self.assertFalse(stabilizer.update("HI")[1])
        self.assertFalse(stabilizer.update("HI")[1])
        self.assertTrue(stabilizer.update("HI")[1])

    def test_duplicate_gesture_is_suppressed_and_new_one_sends(self):
        stabilizer = GestureStabilizer(3)
        for _ in range(3):
            stabilizer.update("HELLO")
        self.assertTrue(stabilizer.update("HI")[1] is False)
        self.assertTrue(stabilizer.update("HI")[1] is False)
        self.assertTrue(stabilizer.update("HI")[1])
        self.assertFalse(stabilizer.update("HI")[1])
        self.assertFalse(stabilizer.update("HELLO")[1])
        self.assertFalse(stabilizer.update("HELLO")[1])
        self.assertTrue(stabilizer.update("HELLO")[1])


if __name__ == "__main__":
    unittest.main()
