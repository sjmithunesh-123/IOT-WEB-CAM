# Hardware test procedure

These are manual checks; repository tests do not prove physical hardware operation.

1. **Firmware startup:** configure the Wi-Fi macros, upload the ESP32 sketch, open Serial at 115200, and record the printed `Wi-Fi connected, IP address` line. Confirm `MPU6050 READY` or record `MPU6050 INIT FAIL`.
2. **I2C scanner:** run `Invoke-RestMethod http://ESP32_IP/i2c` and inspect Serial output. Expect OLED `0x3C` and MPU6050 `0x68`; missing addresses indicate wiring or power faults.
3. **Wi-Fi health:** run `Invoke-RestMethod http://ESP32_IP/health` and confirm `wifi`, `oled`, `audio`, `sd_card`, and `mpu6050` fields.
4. **OLED-only test:** run `Invoke-RestMethod 'http://ESP32_IP/test/oled?text=HELLO'`; expect `ok: true`, `OLED test text: HELLO` in Serial, and `HELLO` on the display.
5. **DFPlayer-only test:** prepare a FAT32 card with `/MP3/001.mp3` through `/MP3/006.mp3`, use stable suitable 5V power and common ground, then run `Invoke-RestMethod 'http://ESP32_IP/test/audio?track=1'`. Expect `DFPlayer test playback: /MP3/001.mp3`.
6. **Webcam:** activate the virtual environment, run `python python_app/main.py --transport wifi --esp32-ip ESP32_IP`, and confirm the live window opens. Try `--camera 1` if camera index 0 is unavailable.
7. **Gesture HTTP:** send `Invoke-RestMethod -Method Post -Uri http://ESP32_IP/gesture -ContentType 'application/json' -Body '{"gesture":"HELLO","pattern":"01111"}'` and confirm HTTP 200, Serial `HTTP gesture received: HELLO pattern=01111`, OLED `Fingers: 01111` and `HELLO`, and one audio attempt.
8. **MediaPipe:** confirm landmarks appear over the hand and the status changes from `NO HAND` to a label. Keep the hand centered and palm-facing during calibration.
9. **MPU6050:** verify `mpu6050: true` from `/health`, then disconnect it and verify `false` plus a clear Serial error. Motion must not change gesture labels.
10. **End to end:** hold each supported pose until stable, verify one HTTP command, one OLED update, and one playback. Change to a different stable pose or release to `NO HAND` before repeating. Holding a pose continuously must not replay it.
11. **Failure behavior:** remove the SD card, disconnect DFPlayer, or stop Wi-Fi and verify the webcam remains open, HTTP health/status reports the failure, and OLED initialization remains independent.

Record actual results separately for the project demonstration log. Do not mark a step passed without performing it on the assembled hardware.

## Browser dashboard validation record

The direct local browser path was tested with the Vite app at `http://localhost:5173/` and ESP32 IP `192.168.31.18`:

- `/health` returned `wifi: true`, `oled: true`, `audio: false`, and `mpu6050: false`.
- The browser health check showed ESP32 `connected` and OLED `initialized`.
- The browser MediaPipe pipeline recognized `HI` with pattern `11111`.
- The browser command was acknowledged, and `/health` then reported `gesture: "HI"`, `pattern: "11111"`, and `message: "AUDIO OFF"`.
- The OLED HTTP test and browser command prove software delivery and OLED initialization; the physical pixels must still be visually confirmed.
- DFPlayer and MPU6050 remain hardware failures and are not counted as passed.
