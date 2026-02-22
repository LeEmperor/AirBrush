#include <Arduino.h>

#define BAUD_USB 115200
#define BAUD_MAIN 115200

#define DAC1_PIN 25
#define DAC2_PIN 26

#define RX_PIN 16
#define TX_PIN 17

HardwareSerial MainSerial(1);

bool started = false;

enum ParseState {
  WAIT_AA,
  WAIT_55,
  READ_C3,
  READ_C4
};

ParseState state = WAIT_AA;

uint8_t c3, c4;

void setup() {

  Serial.begin(BAUD_USB);
  MainSerial.begin(BAUD_MAIN, SERIAL_8N1, RX_PIN, TX_PIN);

  pinMode(DAC1_PIN, OUTPUT);
  pinMode(DAC2_PIN, OUTPUT);

  delay(1000);

  MainSerial.println("READY");
  Serial.println("Sister Ready - Waiting for START");
}

void parseByte(uint8_t b) {

  switch (state) {

    case WAIT_AA:
      if (b == 0xAA) state = WAIT_55;
      break;

    case WAIT_55:
      if (b == 0x55) state = READ_C3;
      else state = WAIT_AA;
      break;

    case READ_C3:
      c3 = b;
      state = READ_C4;
      break;

    case READ_C4:
      c4 = b;

      dacWrite(DAC1_PIN, c3);
      dacWrite(DAC2_PIN, c4);

      Serial.printf("Sister Output -> C3:%d C4:%d\n", c3, c4);

      state = WAIT_AA;
      break;
  }
}

void loop() {
  while (MainSerial.available()) {
    parseByte(MainSerial.read());
  }
}