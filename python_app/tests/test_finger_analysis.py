import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).parents[1]))

from finger_analysis import FingerStateSmoother, joint_angle_degrees, measure_fingers


def points_with_angle(joint_indices, angle):
    """Create a simple 2D bend at the middle point of each selected triple."""
    import math
    points = [[0.0, 0.0, 0.0] for _ in range(21)]
    radians = math.radians(angle)
    for first, pivot, last in joint_indices:
        points[first] = [0.0, 0.0, 0.0]
        points[pivot] = [1.0, 0.0, 0.0]
        points[last] = [1.0 + math.cos(math.pi - radians), math.sin(math.pi - radians), 0.0]
    return points


class FingerAnalysisTests(unittest.TestCase):
    def test_angle_is_180_straight_and_falls_when_bent(self):
        self.assertAlmostEqual(joint_angle_degrees((0, 0), (1, 0), (2, 0)), 180)
        self.assertAlmostEqual(joint_angle_degrees((0, 0), (1, 0), (1, 1)), 90)

    def test_measurements_are_independent_per_finger(self):
        joints = ((2, 3, 4), (5, 6, 7), (9, 10, 11), (13, 14, 15), (17, 18, 19))
        for target, triple in zip(("THUMB", "INDEX", "MIDDLE", "RING", "LITTLE"), joints):
            points = points_with_angle(joints, 170)
            bent_points = points_with_angle((triple,), 80)
            for index in triple:
                points[index] = bent_points[index]
            values = measure_fingers(points)
            with self.subTest(target=target):
                self.assertLess(values[target], 100)
                for name in ("THUMB", "INDEX", "MIDDLE", "RING", "LITTLE"):
                    if name != target:
                        self.assertGreater(values[name], 170)

    def test_thresholds_and_stability_are_independent(self):
        thresholds = {name: (155, 140) for name in ("THUMB", "INDEX", "MIDDLE", "RING", "LITTLE")}
        smoother = FingerStateSmoother(thresholds, 3)
        values = {name: 170.0 for name in thresholds}
        states = smoother.update(values)
        values["INDEX"] = 100.0
        states = smoother.update(values)
        self.assertEqual(states["INDEX"], "STRAIGHT")  # one frame is filtered
        states = smoother.update(values)
        self.assertEqual(states["INDEX"], "BENT")
        self.assertEqual(states["MIDDLE"], "STRAIGHT")

    def test_invalid_thresholds_are_rejected(self):
        thresholds = {name: (155, 140) for name in ("THUMB", "INDEX", "MIDDLE", "RING", "LITTLE")}
        thresholds["INDEX"] = (130, 140)
        with self.assertRaises(ValueError):
            FingerStateSmoother(thresholds)

    def test_incomplete_landmarks_rejected(self):
        with self.assertRaises(ValueError):
            measure_fingers([])


if __name__ == "__main__":
    unittest.main()
