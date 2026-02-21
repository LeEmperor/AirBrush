/**
 * Bench-test servo output — maps normalized stick values to servo angles.
 * Uses ESP32Servo (ledc-based) for clean PWM on any GPIO.
 */
#include "output_servo.h"
#include <ESP32Servo.h>

static Servo yawServo;
static Servo pitchServo;

static const int YAW_PIN   = 18;
static const int PITCH_PIN = 19;
static const int SERVO_MIN = 500;   // µs
static const int SERVO_MAX = 2500;  // µs
static const int SERVO_MID = 1500;

void servoInit() {
  yawServo.attach(YAW_PIN, SERVO_MIN, SERVO_MAX);
  pitchServo.attach(PITCH_PIN, SERVO_MIN, SERVO_MAX);
  yawServo.writeMicroseconds(SERVO_MID);
  pitchServo.writeMicroseconds(SERVO_MID);
}

static int normalized_to_us(float v) {
  // v in [-1, +1] → [SERVO_MIN, SERVO_MAX]
  v = constrain(v, -1.0f, 1.0f);
  return SERVO_MID + (int)(v * (float)(SERVO_MAX - SERVO_MID));
}

void servoWrite(float yaw, float pitch) {
  yawServo.writeMicroseconds(normalized_to_us(yaw));
  pitchServo.writeMicroseconds(normalized_to_us(pitch));
}

void servoNeutral() {
  yawServo.writeMicroseconds(SERVO_MID);
  pitchServo.writeMicroseconds(SERVO_MID);
}
