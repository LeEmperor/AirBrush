/**
 * AirBrush ESP32 firmware.
 *
 * - Connects to Wi-Fi
 * - Receives UDP command packets from the Python server
 * - Drives servos (bench test) and NeoPixel LED strip
 * - Enforces failsafe: neutral output if no packet for >200 ms
 */
#include <Arduino.h>
#include <WiFi.h>
#include <WiFiUdp.h>
#include <Adafruit_NeoPixel.h>

#include "protocol.h"
#include "output_servo.h"
#include "output_ppm.h"

// ── configuration ──────────────────────────────────────────────────────────
static const char* WIFI_SSID     = "AirBrush";       // ← change to your network
static const char* WIFI_PASSWORD = "makemit2026";     // ← change
static const int   UDP_PORT      = 9002;
static const int   FAILSAFE_MS   = 200;

// NeoPixel
static const int   LED_PIN       = 16;
static const int   LED_COUNT     = 8;

// Output mode: true = servo bench test, false = PPM trainer
static const bool  USE_SERVO     = true;
static const int   PPM_PIN       = 25;

// Built-in LED for status
static const int   STATUS_LED    = 2;

// ── globals ────────────────────────────────────────────────────────────────
WiFiUDP udp;
Adafruit_NeoPixel strip(LED_COUNT, LED_PIN, NEO_GRB + NEO_KHZ800);
AirbrushCmd lastCmd;
unsigned long lastPacketMs = 0;
bool inFailsafe = true;
uint32_t lastSeq = 0;

// ── setup ──────────────────────────────────────────────────────────────────
void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println("\n=== AirBrush ESP32 ===");

  pinMode(STATUS_LED, OUTPUT);
  digitalWrite(STATUS_LED, LOW);

  // Wi-Fi
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.printf("Connecting to %s", WIFI_SSID);
  unsigned long t0 = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - t0 < 15000) {
    delay(250);
    Serial.print(".");
  }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("\nConnected!  IP: %s\n", WiFi.localIP().toString().c_str());
  } else {
    Serial.println("\nWi-Fi failed — entering AP mode as fallback");
    WiFi.mode(WIFI_AP);
    WiFi.softAP("AirBrush-ESP", "airbrush32");
    Serial.printf("AP IP: %s\n", WiFi.softAPIP().toString().c_str());
  }

  // UDP
  udp.begin(UDP_PORT);
  Serial.printf("UDP listening on port %d\n", UDP_PORT);

  // outputs
  if (USE_SERVO) {
    servoInit();
    Serial.println("Servo output initialized (GPIO 18/19)");
  } else {
    ppmInit(PPM_PIN);
    Serial.printf("PPM output initialized (GPIO %d)\n", PPM_PIN);
  }

  // NeoPixel
  strip.begin();
  strip.setBrightness(50);
  strip.show();
  Serial.println("NeoPixel ready");

  memset(&lastCmd, 0, sizeof(lastCmd));
}

// ── LED helpers ────────────────────────────────────────────────────────────
void setStripBrightness(float b, bool failsafe) {
  uint8_t bright = (uint8_t)(constrain(b, 0.0f, 1.0f) * 255);
  if (failsafe) {
    // blink red in failsafe
    static bool toggle = false;
    toggle = !toggle;
    for (int i = 0; i < LED_COUNT; i++)
      strip.setPixelColor(i, toggle ? strip.Color(bright, 0, 0) : 0);
  } else {
    for (int i = 0; i < LED_COUNT; i++)
      strip.setPixelColor(i, strip.Color(bright, bright, bright));
  }
  strip.show();
}

// ── main loop ──────────────────────────────────────────────────────────────
void loop() {
  // Read UDP packets
  int packetSize = udp.parsePacket();
  if (packetSize > 0) {
    char buf[512];
    int len = udp.read(buf, sizeof(buf) - 1);
    if (len > 0) {
      buf[len] = '\0';
      AirbrushCmd cmd;
      if (parseCmd(buf, len, cmd)) {
        lastCmd = cmd;
        lastPacketMs = millis();
        lastSeq = cmd.seq;

        Serial.printf("CMD seq=%u  yaw=%.3f  pitch=%.3f  roll=%.3f  "
                      "thr=%.3f  aux1=%.2f  flags=%d\n",
                      cmd.seq, cmd.yaw, cmd.pitch, cmd.roll,
                      cmd.throttle, cmd.aux1, cmd.flags);
      }
    }
  }

  // Failsafe check
  unsigned long elapsed = millis() - lastPacketMs;
  bool wasFailsafe = inFailsafe;
  inFailsafe = (elapsed > FAILSAFE_MS) || lastCmd.failsafe();

  if (inFailsafe && !wasFailsafe) {
    Serial.println(">>> FAILSAFE ENGAGED <<<");
  }
  if (!inFailsafe && wasFailsafe) {
    Serial.println(">>> FAILSAFE CLEARED <<<");
  }

  // Apply outputs
  if (inFailsafe || !lastCmd.armed()) {
    if (USE_SERVO) servoNeutral();
    else           ppmNeutralAll();
  } else {
    if (USE_SERVO) {
      servoWrite(lastCmd.yaw, lastCmd.pitch);
    } else {
      // Standard RC channel mapping: 0=roll, 1=pitch, 2=throttle, 3=yaw
      ppmSetChannel(0, lastCmd.roll);
      ppmSetChannel(1, lastCmd.pitch);
      ppmSetChannel(2, lastCmd.throttle);
      ppmSetChannel(3, lastCmd.yaw);
      ppmSetChannel(4, lastCmd.aux1);
    }
  }

  // LED
  setStripBrightness(lastCmd.aux1, inFailsafe);

  // Status LED — heartbeat blink
  digitalWrite(STATUS_LED, (millis() / 500) % 2);

  delay(5);
}
