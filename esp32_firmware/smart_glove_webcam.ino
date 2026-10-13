#include <Arduino.h>
#include <Wire.h>
#include <WiFi.h>
#include <WebServer.h>
#include <ArduinoJson.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <DFRobotDFPlayerMini.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>

#ifndef SMART_GLOVE_WIFI_SSID
#define SMART_GLOVE_WIFI_SSID "Mithu"
#endif
#ifndef SMART_GLOVE_WIFI_PASSWORD
#define SMART_GLOVE_WIFI_PASSWORD "12345678"
#endif

constexpr uint8_t OLED_WIDTH = 128;
constexpr uint8_t OLED_HEIGHT = 64;
constexpr uint8_t OLED_ADDRESS = 0x3C;
constexpr int OLED_SDA = 21;
constexpr int OLED_SCL = 22;
constexpr int DFPLAYER_RX = 26;  // DFPlayer TX -> ESP32 RX
constexpr int DFPLAYER_TX = 27;  // ESP32 TX -> DFPlayer RX through 1K resistor
constexpr uint32_t USB_BAUD = 115200;
constexpr uint32_t DFPLAYER_BAUD = 9600;
constexpr size_t MAX_COMMAND_LENGTH = 32;
constexpr uint16_t HTTP_PORT = 80;
constexpr uint32_t WIFI_RETRY_INTERVAL_MS = 10000;
constexpr uint32_t WIFI_CONNECT_TIMEOUT_MS = 15000;
constexpr uint8_t MPU6050_ADDRESS = 0x68;

Adafruit_SSD1306 display(OLED_WIDTH, OLED_HEIGHT, &Wire, -1);
HardwareSerial dfSerial(2);
DFRobotDFPlayerMini player;
Adafruit_MPU6050 mpu;
WebServer server(HTTP_PORT);
String commandBuffer;
String currentGesture = "NO HAND";
String currentPattern = "00000";
String currentStatus = "BOOTING";
String lastPlayedGesture;
bool gestureReleased = true;
bool displayReady = false;
bool audioReady = false;
bool mpuReady = false;
bool httpStarted = false;
bool wifiConnecting = false;
bool sdReady = false;
int availableTracks = 0;
uint32_t lastWifiAttempt = 0;
uint32_t wifiConnectStarted = 0;
sensors_event_t lastAcceleration;
sensors_event_t lastGyroscope;

const char* validCommands[] = {
  "HELLO", "HELP ME", "THANK YOU", "WELCOME", "YES", "HI", "UNKNOWN", "NO HAND"
};
constexpr size_t VALID_COMMAND_COUNT = sizeof(validCommands) / sizeof(validCommands[0]);

void handleHealth();
void handleGestureHttp();
void handleOledTest();
void handleAudioTest();
void handleI2cScan();
void handleCorsOptions();
void setScreen(const String& gesture, const String& status);
void playGesture(const String& command);
void startWifiConnection();

bool initializeMpu() {
  for (uint8_t attempt = 1; attempt <= 3; ++attempt) {
    if (mpu.begin(MPU6050_ADDRESS, &Wire)) {
      mpu.setAccelerometerRange(MPU6050_RANGE_8_G);
      mpu.setGyroRange(MPU6050_RANGE_500_DEG);
      mpu.setFilterBandwidth(MPU6050_BAND_21_HZ);
      return true;
    }
    Serial.printf("MPU6050 init attempt %u failed; retrying\n", attempt);
    delay(100);
  }
  return false;
}

bool isAllowedOrigin(const String& origin) {
  return origin == "http://localhost:5173" ||
         origin == "http://127.0.0.1:5173" ||
         origin == "http://localhost:4173" ||
         origin == "http://127.0.0.1:4173";
}

void addCorsHeaders() {
  if (server.hasHeader("Origin") && isAllowedOrigin(server.header("Origin"))) {
    server.sendHeader("Access-Control-Allow-Origin", server.header("Origin"));
    server.sendHeader("Vary", "Origin");
  }
  server.sendHeader("Access-Control-Allow-Methods", "GET,POST,OPTIONS");
  server.sendHeader("Access-Control-Allow-Headers", "Content-Type");
  server.sendHeader("Access-Control-Max-Age", "600");
}

void handleCorsOptions() {
  addCorsHeaders();
  server.send(204);
}

void sendJson(int statusCode, JsonDocument& document) {
  String body;
  serializeJson(document, body);
  addCorsHeaders();
  server.send(statusCode, "application/json", body);
}

void updateDisplay() {
  if (!displayReady) return;
  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);
  display.setTextSize(1);
  display.setCursor(0, 0);
  display.println("SMART GLOVE");
  display.drawFastHLine(0, 10, 128, SSD1306_WHITE);
  display.setCursor(0, 18);
  display.print("Fingers: ");
  display.println(currentPattern);
  display.setCursor(0, 30);
  display.println("GESTURE:");
  display.setCursor(0, 40);
  display.setTextSize(currentGesture.length() <= 7 ? 2 : 1);
  display.println(currentGesture);
  display.setTextSize(1);
  display.setCursor(0, 55);
  display.println(currentStatus);
  display.display();
}

uint8_t scanI2cBus() {
  uint8_t found = 0;
  Serial.println("I2C scan started");
  for (uint8_t address = 1; address < 127; ++address) {
    Wire.beginTransmission(address);
    const uint8_t error = Wire.endTransmission();
    if (error == 0) {
      Serial.printf("I2C device found at 0x%02X\n", address);
      ++found;
    }
  }
  if (found == 0) Serial.println("I2C scan found no devices");
  Serial.printf("I2C scan complete: %u device(s)\n", found);
  return found;
}

void setScreen(const String& gesture, const String& status) {
  if (gesture != currentGesture || status != currentStatus) {
    currentGesture = gesture;
    currentStatus = status;
    updateDisplay();
  }
}

bool isValidPattern(const String& pattern) {
  if (pattern.length() != 5) return false;
  for (uint8_t index = 0; index < 5; ++index) {
    if (pattern[index] != '0' && pattern[index] != '1') return false;
  }
  return true;
}

bool isValidGesture(const String& command) {
  for (size_t i = 0; i < VALID_COMMAND_COUNT; ++i) {
    if (command == validCommands[i]) return true;
  }
  return false;
}

bool processGesture(String command, String& response, const String& pattern = "") {
  command.trim();
  command.toUpperCase();
  if (command.length() == 0) {
    response = "EMPTY_COMMAND";
    return false;
  }
  if (command.length() > MAX_COMMAND_LENGTH) {
    response = "COMMAND_TOO_LONG";
    return false;
  }
  if (!isValidGesture(command)) {
    response = "INVALID_COMMAND";
    return false;
  }
  if (pattern.length() > 0 && !isValidPattern(pattern)) {
    response = "INVALID_PATTERN";
    return false;
  }
  if (pattern.length() > 0) currentPattern = pattern;
  if (command == "NO HAND") {
    gestureReleased = true;
    setScreen("NO HAND", "WAITING");
    response = "NO HAND";
    return true;
  }
  if (command == lastPlayedGesture && !gestureReleased) {
    response = "DUPLICATE";
    return true;
  }
  lastPlayedGesture = command;
  gestureReleased = false;
  setScreen(command, "RECEIVED");
  playGesture(command);
  response = currentStatus;
  return true;
}

int trackFor(const String& command) {
  if (command == "HELLO") return 1;
  if (command == "HELP ME") return 2;
  if (command == "THANK YOU") return 3;
  if (command == "WELCOME") return 4;
  if (command == "YES") return 5;
  if (command == "HI") return 6;
  return 0;
}

void playGesture(const String& command) {
  const int track = trackFor(command);
  if (track == 0) {
    setScreen(command, "NO AUDIO");
    return;
  }
  if (!audioReady) {
    setScreen(command, "AUDIO OFF");
    return;
  }
  if (!sdReady) {
    setScreen(command, "NO SD CARD");
    return;
  }
  if (availableTracks < track) {
    setScreen(command, "TRACK MISSING");
    Serial.printf("ERR %s TRACK_MISSING\n", command.c_str());
    return;
  }
  player.playMp3Folder(track);
  setScreen(command, "PLAYING MP3");
  Serial.printf("ACK %s PLAYING %03d\n", command.c_str(), track);
}

void handleCommand(String command) {
  String response;
  if (processGesture(command, response)) {
    Serial.printf("ACK %s %s\n", command.c_str(), response.c_str());
  } else {
    Serial.printf("ERR %s\n", response.c_str());
  }
}

void handleHealth() {
  StaticJsonDocument<384> document;
  document["status"] = "ok";
  document["wifi"] = WiFi.status() == WL_CONNECTED;
  document["ip"] = WiFi.localIP().toString();
  document["oled"] = displayReady;
  document["audio"] = audioReady;
  document["sd_card"] = sdReady;
  document["tracks"] = availableTracks;
  document["mpu6050"] = mpuReady;
  document["pattern"] = currentPattern;
  document["gesture"] = currentGesture;
  document["message"] = currentStatus;
  sendJson(200, document);
}

void handleOledTest() {
  StaticJsonDocument<192> document;
  if (!displayReady) {
    document["ok"] = false;
    document["error"] = "OLED NOT DETECTED";
    sendJson(503, document);
    return;
  }
  String text = server.hasArg("text") ? server.arg("text") : "HELLO";
  text.trim();
  text.toUpperCase();
  if (text.length() == 0 || text.length() > 16) {
    document["ok"] = false;
    document["error"] = "text must contain 1 to 16 characters";
    sendJson(400, document);
    return;
  }
  setScreen(text, "OLED TEST");
  Serial.printf("OLED test text: %s\n", text.c_str());
  document["ok"] = true;
  document["text"] = text;
  sendJson(200, document);
}

void handleAudioTest() {
  StaticJsonDocument<192> document;
  const int track = server.hasArg("track") ? server.arg("track").toInt() : 1;
  if (track < 1 || track > 6) {
    document["ok"] = false;
    document["error"] = "track must be between 1 and 6";
    sendJson(400, document);
    return;
  }
  if (!audioReady) {
    document["ok"] = false;
    document["error"] = "DFPLAYER INIT FAILED";
    sendJson(503, document);
    return;
  }
  if (!sdReady || availableTracks < track) {
    document["ok"] = false;
    document["error"] = "MP3 TRACK NOT AVAILABLE";
    sendJson(404, document);
    return;
  }
  player.playMp3Folder(track);
  setScreen("AUDIO TEST", "PLAYING");
  Serial.printf("DFPlayer test playback: /MP3/%03d.mp3\n", track);
  document["ok"] = true;
  document["track"] = track;
  sendJson(200, document);
}

void handleI2cScan() {
  const uint8_t count = scanI2cBus();
  StaticJsonDocument<192> document;
  document["ok"] = count > 0;
  document["devices"] = count;
  document["expected_oled"] = "0x3C";
  document["expected_mpu6050"] = "0x68";
  sendJson(200, document);
}

void handleGestureHttp() {
  StaticJsonDocument<160> input;
  const DeserializationError error = deserializeJson(input, server.arg("plain"));
  if (error || !input["gesture"].is<const char*>() || !input["pattern"].is<const char*>()) {
    Serial.println("ERR HTTP /gesture invalid JSON or missing gesture/pattern");
    StaticJsonDocument<128> document;
    document["accepted"] = false;
    document["error"] = "JSON must contain gesture and pattern strings";
    sendJson(400, document);
    return;
  }

  const String incomingPattern = input["pattern"].as<const char*>();
  Serial.printf("HTTP gesture received: %s pattern=%s\n", input["gesture"].as<const char*>(), incomingPattern.c_str());
  String response;
  const bool accepted = processGesture(String(input["gesture"].as<const char*>()), response, incomingPattern);
  StaticJsonDocument<192> document;
  document["accepted"] = accepted && response != "DUPLICATE";
  document["pattern"] = currentPattern;
  document["gesture"] = currentGesture;
  document["message"] = response;
  sendJson(accepted ? 200 : 400, document);
}

void startWifiConnection() {
  if (wifiConnecting || WiFi.status() == WL_CONNECTED) return;
  WiFi.begin(SMART_GLOVE_WIFI_SSID, SMART_GLOVE_WIFI_PASSWORD);
  wifiConnecting = true;
  wifiConnectStarted = millis();
  lastWifiAttempt = wifiConnectStarted;
  Serial.printf("Wi-Fi connecting to %s\n", SMART_GLOVE_WIFI_SSID);
  setScreen(currentGesture, "WIFI WAIT");
}

void maintainWifi() {
  if (WiFi.status() == WL_CONNECTED) {
    wifiConnecting = false;
    if (!httpStarted) {
      server.begin();
      httpStarted = true;
      Serial.print("Wi-Fi connected, IP address: ");
      Serial.println(WiFi.localIP());
      setScreen(currentGesture, "WIFI READY");
    }
    server.handleClient();
    return;
  }
  httpStarted = false;
  if (wifiConnecting) {
    const wl_status_t status = WiFi.status();
    const bool failed = status == WL_NO_SSID_AVAIL || status == WL_CONNECT_FAILED || status == WL_CONNECTION_LOST;
    if (!failed && millis() - wifiConnectStarted < WIFI_CONNECT_TIMEOUT_MS) return;
    wifiConnecting = false;
    WiFi.disconnect(false, false);
    lastWifiAttempt = millis();
    Serial.printf("Wi-Fi connection failed or timed out (status %d)\n", static_cast<int>(status));
    setScreen(currentGesture, "WIFI RETRY");
    return;
  }
  if (millis() - lastWifiAttempt < WIFI_RETRY_INTERVAL_MS) return;
  startWifiConnection();
}

void readMotion() {
  if (mpuReady) {
    sensors_event_t temperature;
    mpu.getEvent(&lastAcceleration, &lastGyroscope, &temperature);
  }
}

void readCommands() {
  while (Serial.available() > 0) {
    const char incoming = static_cast<char>(Serial.read());
    if (incoming == '\n' || incoming == '\r') {
      handleCommand(commandBuffer);
      commandBuffer = "";
    } else if (commandBuffer.length() <= MAX_COMMAND_LENGTH) {
      commandBuffer += incoming;
    } else {
      commandBuffer = "";
      Serial.println("ERR COMMAND_TOO_LONG");
    }
  }
}

void setup() {
  Serial.begin(USB_BAUD);
  Serial.println("ESP32 STARTING");
  currentStatus = "ESP32 STARTING";
  Wire.begin(OLED_SDA, OLED_SCL);
  scanI2cBus();
  displayReady = display.begin(SSD1306_SWITCHCAPVCC, OLED_ADDRESS);
  if (displayReady) {
    currentStatus = "OLED READY";
    updateDisplay();
  } else {
    currentStatus = "OLED ERROR";
    Serial.println("ERR OLED INIT FAIL at address 0x3C");
  }

  dfSerial.begin(DFPLAYER_BAUD, SERIAL_8N1, DFPLAYER_RX, DFPLAYER_TX);
  delay(1000);
  audioReady = player.begin(dfSerial, true, true);
  if (audioReady) {
    player.setTimeOut(1000);
    player.volume(22);
    availableTracks = player.readFileCountsInFolder(1);
    sdReady = availableTracks > 0;
    currentStatus = sdReady ? "AUDIO READY" : "NO SD CARD";
    Serial.printf("DFPlayer ready; /MP3 track count: %d\n", availableTracks);
  } else {
    currentStatus = "AUDIO INIT FAIL";
    Serial.println("ERR DFPLAYER INIT FAIL; check UART, power, and common GND");
  }

  mpuReady = initializeMpu();
  if (mpuReady) {
    Serial.println("MPU6050 READY; motion fusion disabled");
  } else {
    Serial.println("ERR MPU6050 INIT FAIL at address 0x68");
  }

  server.on("/health", HTTP_GET, handleHealth);
  server.on("/health", HTTP_OPTIONS, handleCorsOptions);
  server.on("/gesture", HTTP_POST, handleGestureHttp);
  server.on("/gesture", HTTP_OPTIONS, handleCorsOptions);
  server.on("/test/oled", HTTP_GET, handleOledTest);
  server.on("/test/oled", HTTP_OPTIONS, handleCorsOptions);
  server.on("/test/audio", HTTP_GET, handleAudioTest);
  server.on("/test/audio", HTTP_OPTIONS, handleCorsOptions);
  server.on("/i2c", HTTP_GET, handleI2cScan);
  server.on("/i2c", HTTP_OPTIONS, handleCorsOptions);
  const char* requestHeaders[] = {"Origin", "Access-Control-Request-Method", "Access-Control-Request-Headers"};
  server.collectHeaders(requestHeaders, 3);
  server.onNotFound([]() {
    if (server.method() == HTTP_OPTIONS) {
      addCorsHeaders();
      server.send(204);
      return;
    }
    addCorsHeaders();
    server.send(404, "application/json", "{\"error\":\"not found\"}");
  });
  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.persistent(false);
  startWifiConnection();
  updateDisplay();
  Serial.println(audioReady ? "READY AUDIO_OK" : "READY AUDIO_OFF");
}

void loop() {
  readCommands();
  maintainWifi();
  readMotion();
}
