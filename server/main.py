#!/usr/bin/env python3
"""AirBrush — main entry point.

Starts:
  1. WebSocket + static file server  (for phone client)
  2. Control loop  (pose → commands at ESP_SEND_HZ)
  3. UDP heartbeat to ESP
  4. (Optional) CV camera tracking in a background thread
"""

from __future__ import annotations
import asyncio
import logging
import signal
import sys
import time

import config
import ws_server
from control_mapping import ControlMapper
from udp_link import UDPLink

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL, logging.INFO),
    format="%(asctime)s  %(name)-12s  %(levelname)-5s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("main")

# ── shared objects ──────────────────────────────────────────────────────────
ctrl = ControlMapper()
udp = UDPLink()
ws_server.controller = ctrl
ws_server.udp = udp

# optional CV pose source (populated if cv module loads)
cv_pose: dict | None = None


# ── CV background thread (lazy import) ─────────────────────────────────────
def _start_cv_thread():
    global cv_pose
    if not config.CV_ENABLED:
        log.info("CV disabled (set CV_ENABLED=True to enable)")
        return
    try:
        from cv.camera_pose import CameraPoseEstimator
    except ImportError as exc:
        log.warning("CV module unavailable: %s", exc)
        return

    import threading

    estimator = CameraPoseEstimator(
        camera_index=config.CAMERA_INDEX,
        marker_id=config.MARKER_ID,
        marker_size=config.MARKER_SIZE_M,
    )

    def _cv_loop():
        global cv_pose
        log.info("CV thread started (camera %d)", config.CAMERA_INDEX)
        for pose in estimator.stream():
            cv_pose = pose

    t = threading.Thread(target=_cv_loop, daemon=True, name="cv")
    t.start()


# ── control loop ────────────────────────────────────────────────────────────
async def control_loop():
    interval = 1.0 / config.ESP_SEND_HZ
    log.info("Control loop at %d Hz → ESP %s:%d",
             config.ESP_SEND_HZ, config.ESP_IP, config.ESP_PORT)
    while True:
        now = time.time()

        cv_yaw = cv_pitch = None
        if cv_pose is not None:
            cv_yaw = cv_pose.get("yaw")
            cv_pitch = cv_pose.get("pitch")

        if ctrl.stale:
            flags = ctrl.flags | 2  # set failsafe bit
            udp.send_esp(yaw=0, pitch=0, roll=0, throttle=0,
                         aux1=ctrl.brightness, flags=flags)
        else:
            yaw, pitch, roll = ctrl.compute(cv_yaw, cv_pitch, now)
            udp.send_esp(yaw=yaw, pitch=pitch, roll=roll, throttle=0.0,
                         aux1=ctrl.brightness, flags=ctrl.flags)

        udp.send_pi(brightness=ctrl.brightness, color=ctrl.color,
                     pan=ctrl.cmd_yaw, tilt=ctrl.cmd_pitch)

        await asyncio.sleep(interval)


# ── main ────────────────────────────────────────────────────────────────────
async def main():
    _start_cv_thread()
    await asyncio.gather(
        ws_server.start(),
        control_loop(),
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Shutting down")
        udp.close()
