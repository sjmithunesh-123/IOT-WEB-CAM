# Hardware connections

| Device | Pin | ESP32 / connection |
|---|---|---|
| SSD1306 OLED | SDA | GPIO21 |
| SSD1306 OLED | SCL | GPIO22 |
| SSD1306 OLED | VCC | 3.3V, subject to module specification |
| SSD1306 OLED | GND | GND |
| DFPlayer Mini | TX | GPIO26 (ESP32 RX) |
| DFPlayer Mini | RX | GPIO27 (ESP32 TX), approximately 1K ohm series resistor |
| DFPlayer Mini | VCC | Stable suitable 5V supply |
| DFPlayer Mini | GND | Common GND |
| Speaker | terminals | DFPlayer SPK1 and SPK2 |
| MPU6050 | SDA | GPIO21, shared with OLED |
| MPU6050 | SCL | GPIO22, shared with OLED |
| MPU6050 | VCC/GND | 3.3V/GND according to the module specification |

The ESP32 USB cable supplies programming and Serial diagnostics. Wi-Fi carries gesture commands after the ESP32 joins the configured 2.4 GHz network. Do not connect the speaker to an ESP32 GPIO. Do not reverse DFPlayer TX/RX. Use a stable suitable 5V supply for the DFPlayer, connect all grounds, and verify supply voltage before power-up.

No flex sensor is required in webcam mode.
