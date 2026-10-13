import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).parents[1]))

from serial_communication import Esp32Serial, SerialStatus


class FakeSerial:
    is_open = True

    def __init__(self):
        self.writes = []

    def write(self, data):
        self.writes.append(data)
        return len(data)

    def readline(self):
        return b"ACK HI PLAYING 002\n"

    def close(self):
        self.is_open = False


class SerialTransportTests(unittest.TestCase):
    def test_valid_command_is_written_once_and_ack_is_recorded(self):
        transport = Esp32Serial("COM_TEST")
        fake = FakeSerial()
        transport._serial = fake
        transport.status = SerialStatus(connected=True)

        self.assertTrue(transport.send("hi"))
        self.assertEqual(fake.writes, [b"HI\n"])
        self.assertEqual(transport.status.last_response, "ACK HI PLAYING 002")

    def test_invalid_command_never_reaches_transport(self):
        transport = Esp32Serial("COM_TEST")
        fake = FakeSerial()
        transport._serial = fake
        transport.status = SerialStatus(connected=True)

        self.assertFalse(transport.send("PLAY 999"))
        self.assertEqual(fake.writes, [])


if __name__ == "__main__":
    unittest.main()
