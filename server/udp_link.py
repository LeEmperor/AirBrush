"""UDP sender for ESP and Pi command packets."""

from __future__ import annotations
import asyncio
import json
import logging
import socket
import time

import config

log = logging.getLogger("udp_link")

_seq = 0


def _next_seq() -> int:
    global _seq
    _seq += 1
    return _seq


class UDPLink:
    """Non-blocking UDP sender (one socket, reusable for multiple targets)."""

    def __init__(self):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setblocking(False)

    # ── ESP command ─────────────────────────────────────────────────────
    def send_esp(self, yaw=0.0, pitch=0.0, roll=0.0, throttle=0.0,
                 aux1=0.0, flags=0):
        pkt = {
            "t": time.time(),
            "seq": _next_seq(),
            "yaw": round(yaw, 4),
            "pitch": round(pitch, 4),
            "roll": round(roll, 4),
            "throttle": round(throttle, 4),
            "aux1": round(aux1, 4),
            "flags": flags,
        }
        raw = json.dumps(pkt, separators=(",", ":")).encode()
        try:
            self._sock.sendto(raw, (config.ESP_IP, config.ESP_PORT))
            self._esp_ok = True
        except BlockingIOError:
            pass
        except OSError as exc:
            if getattr(self, "_esp_ok", True):
                log.warning("ESP send error (suppressing repeats): %s", exc)
                self._esp_ok = False

    # ── Pi LED command ──────────────────────────────────────────────────
    def send_pi(self, brightness=0.5, color=(255, 255, 255),
                pan=0.0, tilt=0.0):
        pkt = {
            "brightness": round(brightness, 3),
            "color": list(color),
            "pan": round(pan, 4),
            "tilt": round(tilt, 4),
        }
        raw = json.dumps(pkt, separators=(",", ":")).encode()
        try:
            self._sock.sendto(raw, (config.PI_IP, config.PI_PORT))
        except (BlockingIOError, OSError) as exc:
            log.debug("Pi send error: %s", exc)

    # ── heartbeat (call periodically even when idle) ────────────────────
    def send_heartbeat(self):
        self.send_esp(flags=0)

    def close(self):
        self._sock.close()
