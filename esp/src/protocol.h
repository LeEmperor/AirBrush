/**
 * AirBrush protocol definitions.
 * Server → ESP UDP JSON v1 packet parsing.
 */
#pragma once
#include <Arduino.h>

struct AirbrushCmd {
  float t;
  uint32_t seq;
  float yaw;       // -1 .. +1
  float pitch;     // -1 .. +1
  float roll;      // -1 .. +1
  float throttle;  // -1 .. +1 (keep ~0 for rotation-only)
  float aux1;      // 0..1 brightness
  uint8_t flags;   // bit0: armed, bit1: failsafe

  bool armed() const    { return flags & 0x01; }
  bool failsafe() const { return flags & 0x02; }
};

/**
 * Parse a JSON command packet into AirbrushCmd.
 * Uses a minimal hand-rolled parser to avoid pulling in ArduinoJson.
 * Expects keys: t, seq, yaw, pitch, roll, throttle, aux1, flags.
 */
inline bool parseCmd(const char* json, size_t len, AirbrushCmd& cmd) {
  // Zero out
  memset(&cmd, 0, sizeof(cmd));

  String s(json);

  auto extractFloat = [&](const char* key) -> float {
    int idx = s.indexOf(key);
    if (idx < 0) return 0.0f;
    idx = s.indexOf(':', idx);
    if (idx < 0) return 0.0f;
    return s.substring(idx + 1).toFloat();
  };

  auto extractInt = [&](const char* key) -> int {
    int idx = s.indexOf(key);
    if (idx < 0) return 0;
    idx = s.indexOf(':', idx);
    if (idx < 0) return 0;
    return s.substring(idx + 1).toInt();
  };

  cmd.t        = extractFloat("\"t\"");
  cmd.seq      = (uint32_t)extractInt("\"seq\"");
  cmd.yaw      = extractFloat("\"yaw\"");
  cmd.pitch    = extractFloat("\"pitch\"");
  cmd.roll     = extractFloat("\"roll\"");
  cmd.throttle = extractFloat("\"throttle\"");
  cmd.aux1     = extractFloat("\"aux1\"");
  cmd.flags    = (uint8_t)extractInt("\"flags\"");

  return cmd.seq > 0 || s.indexOf("\"seq\"") >= 0;
}
