#define DAC_1 25
#define DAC_2 26
#define LED_BUILTIN 2
#define TEST_LED 4
//heartbeat packet:
//2 byte header + 2 byte ID
//0 byte payload
//2 byte ID + 2 byte footer

//control packet
//2 byte header + 2 byte ID
//4 byte payload
//2 byte ID + 2 byte footer

const uint16_t heartbeat_id = 0x0000;
const uint16_t control_id = 0x0001;
const uint16_t delimiter = 0xF0F0;
unsigned long last_heartbeat_received_time = 0;
bool heartbeat_packets_started = false;

hw_timer_t* Timer0_Cfg = NULL;

uint8_t raw_buf[12] = {0};
typedef struct {
  uint16_t header;
  uint16_t header_id;
  uint16_t footer_id;
  uint16_t footer;
} HEARTBEAT_PACKET;

typedef struct {
  uint16_t header;
  uint16_t header_id;
  uint8_t payload[4];
  uint16_t footer_id;
  uint16_t footer;
} CONTROL_PACKET;

void ARDUINO_ISR_ATTR watchdogISR() {
  digitalWrite(LED_BUILTIN, !digitalRead(LED_BUILTIN));
  if ((last_heartbeat_received_time > 2000) && heartbeat_packets_started == true) {
    digitalWrite(TEST_LED, !digitalRead(TEST_LED));
  }
  else if ((last_heartbeat_received_time <= 2000) && heartbeat_packets_started == true) {
    digitalWrite(LED_BUILTIN, !digitalRead(LED_BUILTIN));
  }
}

void setup() {
  Serial.begin(115200, SERIAL_8N1);
  Timer0_Cfg = timerBegin(1000000);
  pinMode(LED_BUILTIN, OUTPUT);
  pinMode(TEST_LED, OUTPUT);
  digitalWrite(LED_BUILTIN, LOW);
  digitalWrite(TEST_LED, LOW);
  timerAttachInterrupt(Timer0_Cfg, &watchdogISR);
  timerAlarm(Timer0_Cfg, 1000000, true, 0);
}

bool all255() {
  bool allFF = true;
  for (int i = 0; i < 12; i++) {
    if (raw_buf[i] != 0xFF) {
      allFF = false;
    }
  }
  return allFF;
}

void loop() {
  int i = 0;
  while (Serial.available() && i < 12) {
     char c = Serial.read();
     raw_buf[i] = c;
     i++;
  }
  
  if (!all255()) {
    for (int i = 0; i < 12; i++) {
      Serial.write(raw_buf[i]);
    }
  }
  
  for (int i = 0; i < 12; i++) {
      raw_buf[i] = 0xFF;
  }

  



  delay(10);


//   if (Serial.available()) {
//     HEARTBEAT_PACKET hb;
//     CONTROL_PACKET ctrl;
//     uint8_t temp_header[2];
//     uint8_t temp_id[2];
//     Serial.read(temp_header, 4);
//     if (!(temp_header[0] == 0xF0 && temp_header[1] == 0xF0)) {
//    //   Serial.println("Invalid packet!");
//       while(Serial.available()) {
//         Serial.read();
//       }
//     }
//     else {
//       Serial.read(temp_id, 4);
//       if (temp_id[0] == 0x00 && temp_id[1] == 0x00) {
//         //heartbeat packet
//         if (heartbeat_packets_started == false) {
//           heartbeat_packets_started = true;
//         }
//         for (int i = 0; i < 2; i++) {
//           hb.header[i] = temp_header[i];
//         }
//         for (int i = 0; i < 2; i++) {
//           hb.header_id[i] = temp_id[i];
//         }
//         Serial.read(hb.footer_id, 2);
//         Serial.read(hb.footer, 2);
//         last_heartbeat_received_time = millis();

//         Serial.write(hb.payload, 4);
//         Serial.write('\n');

//       }
//       else if (temp_id[0] == 0x01 && temp_id[1] == 0x00) {
//         for (int i = 0; i < 2; i++) {
//           ctrl.header[i] = temp_header[i];
//         }
//         for (int i = 0; i < 2; i++) {
//           ctrl.header_id[i] = temp_id[i];
//         }
//         Serial.read(ctrl.payload, 4);
//         Serial.read(ctrl.footer_id, 2);
//         Serial.read(ctrl.footer, 2);

//         Serial.write(ctrl.payload, 4);
//         Serial.write('\n');

//       }
//     else {
//  //     Serial.println("Invalid packet id!");
//       while(Serial.available()) {
//         Serial.read();
//       }
//     }
//   }
//   }
}
