#!/usr/bin/env python3
"""AirBrush Raspberry Pi LED service.

Listens for UDP JSON packets from the server and drives a PWM LED.
Falls back to stub mode if GPIO is unavailable (for testing on non-Pi).

Packet format:
    { "brightness": 0.6, "color": [255,180,120], "pan": 0.1, "tilt": -0.2 }

Usage:
    python light_server.py [--port 9003]
"""

from __future__ import annotations
import argparse
import json
import logging
import socket
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(name)-10s  %(levelname)-5s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("light")

# ── GPIO setup (graceful fallback) ──────────────────────────────────────────
LED_PIN = 18  # BCM pin for hardware PWM

try:
    import lgpio
    _chip = lgpio.gpiochip_open(0)
    lgpio.gpio_claim_output(_chip, LED_PIN)

    def set_led_pwm(brightness: float):
        duty = max(0, min(100, brightness * 100))
        lgpio.tx_pwm(_chip, LED_PIN, 1000, duty)

    log.info("GPIO initialized on pin %d", LED_PIN)

except Exception as exc:
    log.warning("GPIO unavailable (%s) — running in stub mode", exc)

    def set_led_pwm(brightness: float):
        log.debug("LED stub: brightness=%.2f", brightness)


# ── main loop ───────────────────────────────────────────────────────────────
def run(port: int = 9003):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", port))
    sock.settimeout(1.0)
    log.info("Listening on UDP :%d", port)

    last_log_t = 0.0
    brightness = 0.0

    while True:
        try:
            data, addr = sock.recvfrom(1024)
        except socket.timeout:
            continue
        except KeyboardInterrupt:
            break

        try:
            msg = json.loads(data.decode())
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue

        brightness = msg.get("brightness", brightness)
        color = msg.get("color", [255, 255, 255])
        pan = msg.get("pan", 0.0)
        tilt = msg.get("tilt", 0.0)

        set_led_pwm(brightness)

        now = time.time()
        if now - last_log_t > 2.0:
            log.info("brightness=%.2f  color=%s  pan=%.2f  tilt=%.2f",
                     brightness, color, pan, tilt)
            last_log_t = now


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=9003)
    run(ap.parse_args().port)
