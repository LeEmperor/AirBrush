#include <Arduino.h>

#define BAUDRATE 115200

#define PACKET_DELIMITER 0xF0F0
#define HEARTBEAT_PACKET_ID 0x00
#define CONTROL_PACKET_ID   0x01

#define DAC1_PIN 25
#define DAC2_PIN 26

#define MAX_PACKET_SIZE 12   // largest possible packet

enum ParseState {
  WAIT_HEADER_1,
  WAIT_HEADER_2,
  READ_ID_1,
  READ_ID_2,
  READ_REST
};

ParseState state = WAIT_HEADER_1;

uint8_t buffer[MAX_PACKET_SIZE];
uint8_t indexPos = 0;
uint8_t expectedLength = 0;
uint16_t packet_id = 0;

void resetParser() {
  state = WAIT_HEADER_1;
  indexPos = 0;
  expectedLength = 0;
}

void processPacket() {
  if (packet_id == CONTROL_PACKET_ID) {
    uint8_t control1 = buffer[4];
    uint8_t control2 = buffer[5];

    dacWrite(DAC1_PIN, control1);
    dacWrite(DAC2_PIN, control2);

    Serial.printf("Control1: %d  Control2: %d\n", control1, control2);
  }
  else if (packet_id == HEARTBEAT_PACKET_ID) {
    Serial.println("Heartbeat received");
  }
}

void parseByte(uint8_t byteIn) {

  switch (state) {

    case WAIT_HEADER_1:
      if (byteIn == 0xF0) {
        buffer[0] = byteIn;
        state = WAIT_HEADER_2;
      }
      break;

    case WAIT_HEADER_2:
      if (byteIn == 0xF0) {
        buffer[1] = byteIn;
        state = READ_ID_1;
      } else {
        state = WAIT_HEADER_1;
      }
      break;

    case READ_ID_1:
      buffer[2] = byteIn;
      state = READ_ID_2;
      break;

    case READ_ID_2:
      buffer[3] = byteIn;
      packet_id = buffer[2] | (buffer[3] << 8);

      if (packet_id == HEARTBEAT_PACKET_ID) {
        expectedLength = 8;
      }
      else if (packet_id == CONTROL_PACKET_ID) {
        expectedLength = 12;
      }
      else {
        resetParser(); // unknown packet
        break;
      }

      indexPos = 4;
      state = READ_REST;
      break;

    case READ_REST:
      buffer[indexPos++] = byteIn;

      if (indexPos >= expectedLength) {

        uint16_t footer_id =
          buffer[expectedLength - 4] |
          (buffer[expectedLength - 3] << 8);

        uint16_t footer_delim =
          buffer[expectedLength - 2] |
          (buffer[expectedLength - 1] << 8);

        if (footer_delim == PACKET_DELIMITER &&
            footer_id == packet_id) {

          processPacket();
        }

        resetParser();
      }
      break;
  }
}

void setup() {
  Serial.begin(BAUDRATE);
  delay(1000);

  pinMode(DAC1_PIN, OUTPUT);
  pinMode(DAC2_PIN, OUTPUT);

  Serial.println("ESP32 Receiver Ready");
}

void loop() {
  while (Serial.available()) {
    parseByte(Serial.read());
  }
}