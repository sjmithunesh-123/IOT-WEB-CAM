# Troubleshooting

## `MediaPipe model missing`
Download the official Hand Landmarker `.task` model and save it exactly as `assets/models/hand_landmarker.task`. Do not rename a different model or create a placeholder.

## `Unable to open webcam`
Close other camera applications, check Windows camera privacy permissions, and try `--camera 1` or another index.

## ESP32 is disconnected
Check the ESP32 Serial Monitor for `Wi-Fi connected, IP address`, then run `Invoke-RestMethod http://ESP32_IP/health`. Confirm the laptop and ESP32 are on the same 2.4 GHz network. For the preserved USB fallback, run `python python_app/main.py --list-ports`, select the port assigned by Windows, and close Arduino Serial Monitor.

## Wi-Fi does not connect
Replace `SMART_GLOVE_WIFI_SSID` and `SMART_GLOVE_WIFI_PASSWORD` with the actual 2.4 GHz network credentials before compiling. The firmware retries without blocking the sensor loop. Confirm the printed IP, firewall rules, and that `SMART_GLOVE_ESP32_IP` or `--esp32-ip` matches it.

## OLED is blank
Check 3.3V/GND, SDA/SCL, and the `0x3C` address. Some modules use a different address and require an explicit firmware change.

## `AUDIO INIT FAIL`, `NO SD CARD`, or `TRACK MISSING`
Check stable 5V power, common ground, FAT32 formatting, file names under `/MP3`, speaker wiring to SPK1/SPK2, and the DFPlayer TX/RX directions. OLED operation should continue even when audio fails.

The firmware uses UART2 on GPIO26 (ESP32 RX, connected to DFPlayer TX) and GPIO27
(ESP32 TX, connected to DFPlayer RX through approximately 1K ohm). GPIO34 is
input-only and must not be used for this UART RX connection because it cannot
provide an internal pull-up. A short startup delay is included for the
DFPlayer power-up sequence, but the module still requires a stable suitable 5V
supply and a common ground with the ESP32.

## `MPU6050 INIT FAIL`

If the I2C scan reports `0x68` but initialization still fails, check that the
MPU6050 module is powered according to its module specification, that SDA/SCL
are connected to GPIO21/GPIO22, and that all grounds are common. The firmware
retries initialization three times after the scan. A persistent failure after
those retries means the device is responding at the bus address but is not
identifying as a compatible MPU6050 (or has an electrical/power problem).
Check that the sensor shares GPIO21 SDA and GPIO22 SCL with the OLED, uses the expected `0x68` address, has correct power and ground, and is not shorting the I2C bus. Motion data is diagnostic only and does not affect gesture classification.

## Labels are unstable
Use good lighting, keep one hand visible, keep the palm facing the camera, and allow the configured five-frame stability window. Unsupported poses intentionally become `UNKNOWN`; this project does not claim complete sign-language translation.
