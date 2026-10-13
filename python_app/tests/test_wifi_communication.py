import sys
from pathlib import Path
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1]))

from wifi_communication import Esp32Wifi


class FakeResponse:
    def __init__(self, code=200, body=b'{"status":"ok"}'):
        self.code = code
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def getcode(self):
        return self.code

    def read(self):
        return self.body


class WifiTransportTests(unittest.TestCase):
    @patch("wifi_communication.urlopen")
    def test_health_and_gesture_use_expected_http_requests(self, urlopen):
        urlopen.side_effect = [FakeResponse(), FakeResponse(body=b'{"accepted":true}')]
        transport = Esp32Wifi("192.168.1.42", 8080, 0.5)

        self.assertTrue(transport.connect())
        self.assertTrue(transport.send("thank   you", "11011"))
        self.assertEqual(urlopen.call_count, 2)
        health_request = urlopen.call_args_list[0].args[0]
        gesture_request = urlopen.call_args_list[1].args[0]
        self.assertEqual(health_request.full_url, "http://192.168.1.42:8080/health")
        self.assertEqual(gesture_request.full_url, "http://192.168.1.42:8080/gesture")
        self.assertEqual(gesture_request.data, b'{"gesture": "THANK YOU", "pattern": "11011"}')
        self.assertEqual(transport.status.last_response, '{"accepted":true}')

    @patch("wifi_communication.urlopen")
    def test_invalid_command_never_reaches_http(self, urlopen):
        transport = Esp32Wifi("192.168.1.42")
        self.assertFalse(transport.send("PLAY 999"))
        urlopen.assert_not_called()

    @patch("wifi_communication.urlopen")
    def test_invalid_pattern_never_reaches_http(self, urlopen):
        transport = Esp32Wifi("192.168.1.42")
        self.assertFalse(transport.send("HELLO", "0123"))
        urlopen.assert_not_called()

    @patch("wifi_communication.urlopen")
    def test_connection_failure_is_reported_without_raising(self, urlopen):
        urlopen.side_effect = OSError("offline")
        transport = Esp32Wifi("192.168.1.42")
        self.assertFalse(transport.connect())
        self.assertFalse(transport.status.connected)
        self.assertIn("offline", transport.status.last_error)


if __name__ == "__main__":
    unittest.main()
