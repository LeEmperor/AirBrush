#include <Arduino.h>

#define BAUD_USB 115200
#define BAUD_SISTER 115200

#define PACKET_DELIMITER 0xF0F0
#define HEARTBEAT_PACKET_ID 0x00
#define CONTROL_PACKET_ID   0x01

#define DAC1_PIN 25
#define DAC2_PIN 26

#define SISTER_TX 17
#define SISTER_RX 16

#define MAX_PACKET_SIZE 12

HardwareSerial SisterSerial(1);

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
}

void forwardToSister(uint8_t c3, uint8_t c4) {
  SisterSerial.write(0xAA);
  SisterSerial.write(0x55);
  SisterSerial.write(c3);
  SisterSerial.write(c4);
}

void processPacket() {

  if (packet_id == CONTROL_PACKET_ID) {

    uint8_t c1 = buffer[4];
    uint8_t c2 = buffer[5];
    uint8_t c3 = buffer[6];
    uint8_t c4 = buffer[7];

    dacWrite(DAC1_PIN, c1);
    dacWrite(DAC2_PIN, c2);

    forwardToSister(c3, c4);

    Serial.printf("Main -> C1:%d C2:%d | Forwarded C3:%d C4:%d\n",
                  c1, c2, c3, c4);
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
      } else state = WAIT_HEADER_1;
      break;

    case READ_ID_1:
      buffer[2] = byteIn;
      state = READ_ID_2;
      break;

    case READ_ID_2:
      buffer[3] = byteIn;
      packet_id = buffer[2] | (buffer[3] << 8);
      expectedLength = (packet_id == CONTROL_PACKET_ID) ? 12 : 8;
      indexPos = 4;
      state = READ_REST;
      break;

    case READ_REST:
      buffer[indexPos++] = byteIn;
      if (indexPos >= expectedLength) {
        uint16_t footer =
          buffer[expectedLength-2] |
          (buffer[expectedLength-1] << 8);
        if (footer == PACKET_DELIMITER) {
          processPacket();
        }
        resetParser();
      }
      break;
  }
}

void setup() {

  Serial.begin(BAUD_USB);
  SisterSerial.begin(BAUD_SISTER, SERIAL_8N1, SISTER_RX, SISTER_TX);

  pinMode(DAC1_PIN, OUTPUT);
  pinMode(DAC2_PIN, OUTPUT);

  Serial.println("Main ESP32 Ready");
}

void loop() {
  while (Serial.available()) {
    parseByte(Serial.read());
  }
}