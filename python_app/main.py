"""Entry point for the Smart Glove webcam demonstrator."""
import argparse
import logging

from config import AppConfig
from gesture_recognition import GestureStabilizer
from hand_landmarks import HandLandmarkDetector
from serial_communication import Esp32Serial
from wifi_communication import Esp32Wifi
from webcam import run_camera


def main() -> int:
    parser = argparse.ArgumentParser(description="Webcam sign-pose demonstrator for ESP32")
    parser.add_argument("--transport", choices=("wifi", "serial"), help="Command transport (default: SMART_GLOVE_TRANSPORT or wifi)")
    parser.add_argument("--port", help="ESP32 COM port, e.g. COM5")
    parser.add_argument("--camera", type=int, help="Camera index")
    parser.add_argument("--esp32-ip", help="ESP32 Wi-Fi IP address")
    parser.add_argument("--http-port", type=int, help="ESP32 HTTP server port")
    parser.add_argument("--list-ports", action="store_true", help="List serial ports and exit")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    defaults = AppConfig()
    config = AppConfig(
        transport=args.transport or defaults.transport,
        serial_port=args.port if args.port is not None else AppConfig().serial_port,
        camera_index=args.camera if args.camera is not None else AppConfig().camera_index,
        esp32_ip=args.esp32_ip if args.esp32_ip is not None else defaults.esp32_ip,
        esp32_http_port=args.http_port if args.http_port is not None else defaults.esp32_http_port,
    )
    if args.list_ports:
        print("\n".join(Esp32Serial.list_ports()))
        return 0
    sender = (
        Esp32Wifi(config.esp32_ip, config.esp32_http_port, config.http_timeout)
        if config.transport == "wifi"
        else Esp32Serial(config.serial_port, config.serial_baudrate)
    )
    if not sender.connect():
        logging.warning("ESP32 is offline: %s", sender.status.last_error)
    detector = None
    try:
        detector = HandLandmarkDetector(config.model_path, config.min_detection_confidence, config.min_presence_confidence, config.min_tracking_confidence)
        run_camera(config, detector, sender, GestureStabilizer(config.stability_window))
    except (FileNotFoundError, OSError, RuntimeError) as exc:
        logging.error("Webcam application stopped: %s", exc)
        return 1
    finally:
        try:
            if detector is not None:
                detector.close()
        finally:
            sender.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
