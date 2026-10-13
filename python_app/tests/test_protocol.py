import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).parents[1]))

from config import AUDIO_TRACKS
from protocol import encode_command, is_valid_command


class ProtocolTests(unittest.TestCase):
    def test_supported_commands(self):
        for command in ("HELLO", "HELP ME", "THANK YOU", "WELCOME", "YES", "HI", "UNKNOWN", "NO HAND"):
            self.assertTrue(is_valid_command(command))

    def test_invalid_command_rejected(self):
        self.assertFalse(is_valid_command("PLAY 999"))
        with self.assertRaises(ValueError):
            encode_command("arbitrary webcam text")

    def test_command_is_newline_terminated(self):
        self.assertEqual(encode_command("thank   you"), b"THANK YOU\n")

    def test_audio_mapping(self):
        self.assertEqual(AUDIO_TRACKS, {
            "HELLO": 1,
            "HELP ME": 2,
            "THANK YOU": 3,
            "WELCOME": 4,
            "YES": 5,
            "HI": 6,
        })


if __name__ == "__main__":
    unittest.main()
