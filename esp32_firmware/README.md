# ESP32 firmware

## Libraries

Install these Arduino libraries before compiling:

- Adafruit GFX Library
- Adafruit SSD1306
- DFRobotDFPlayerMini
- ArduinoJson
- Adafruit MPU6050

The firmware uses the ESP32 Arduino core, `HardwareSerial(2)` for the DFPlayer, and a 2.4 GHz station Wi-Fi connection. USB commands remain on the default `Serial` channel at 115200 baud as a diagnostic fallback. Set `SMART_GLOVE_WIFI_SSID` and `SMART_GLOVE_WIFI_PASSWORD` before compiling; the assigned IP is printed at startup.

## Wiring

- OLED SDA: GPIO21; SCL: GPIO22; I2C address: `0x3C`
- DFPlayer TX -> ESP32 GPIO26 (RX)
- ESP32 GPIO27 (TX) -> DFPlayer RX through approximately 1K ohm
- DFPlayer speaker: SPK1/SPK2
- DFPlayer power: stable suitable 5V supply; all grounds common
- MPU6050 SDA/SCL: GPIO21/GPIO22, normally address `0x68`, shared with the OLED I2C bus

Never connect the speaker to an ESP32 GPIO.

## SD card

Use a FAT32 microSD card and place files in `/MP3` with these names:

`/MP3/001.mp3` through `/MP3/006.mp3`

The Python labels map to tracks as follows: `HELLO=001.mp3`, `HELP ME=002.mp3`, `THANK YOU=003.mp3`, `WELCOME=004.mp3`, `YES=005.mp3`, and `HI=006.mp3`. `UNKNOWN` and `NO HAND` do not play audio. The firmware checks the reported `/MP3` folder count and reports a missing track without stopping OLED operation. Playback uses `DFRobotDFPlayerMini::playMp3Folder(track)`, which addresses files in the `/MP3` folder by numeric index.

## HTTP endpoints

- `GET /health` returns Wi-Fi, OLED, audio, MPU6050, current gesture, and status fields.
- `POST /gesture` accepts JSON such as `{ "gesture": "HELLO", "pattern": "01111" }` and returns HTTP 200 for accepted or duplicate commands, and HTTP 400 for malformed or invalid commands.
- `GET /i2c` scans the shared bus and prints all detected addresses to Serial.
- `GET /test/oled?text=HELLO` tests OLED output without MediaPipe.
- `GET /test/audio?track=1` tests one available `/MP3/001.mp3` file without MediaPipe.

Motion data is read for health/debugging only. It is not fused into gesture classification.

## Manual serial test

With the Arduino Serial Monitor closed before starting Python, a serial terminal at 115200 can send one line at a time:

```text
HELLO
HELP ME
THANK YOU
WELCOME
YES
HI
UNKNOWN
NO HAND
```

The firmware replies with `ACK ...` or `ERR ...`. Sending the same gesture while it is playing is suppressed.
