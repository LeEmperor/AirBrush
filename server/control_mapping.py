"""Map phone pose (quaternion) to drone/servo commands.

Two modes:
  yaw_pitch — drone yaws, servo handles pitch. Safest for indoor use.
  full      — drone yaw + pitch + roll. Advanced; prop guards required.
"""

from __future__ import annotations
import logging
import math
import time

import config
from filters import (EMAFilter, PID, quat_to_euler, relative_quat,
                      angle_wrap)

log = logging.getLogger("control")


class ControlMapper:
    def __init__(self):
        self.mode: str = config.CONTROL_MODE
        self.armed: bool = False
        self.brightness: float = config.DEFAULT_BRIGHTNESS
        self.color: tuple = (255, 255, 255)

        # calibration reference quaternion (set by "calibrate_zero")
        self._ref_quat: list | None = None

        # smoothing on the derived yaw/pitch setpoints
        self._yaw_ema = EMAFilter(config.SMOOTHING_ALPHA)
        self._pitch_ema = EMAFilter(config.SMOOTHING_ALPHA)

        # PID controllers (used when CV measurement is available)
        self._yaw_pid = PID(kp=config.PID_KP, ki=config.PID_KI,
                            kd=config.PID_KD)
        self._pitch_pid = PID(kp=config.PID_PITCH_KP, ki=config.PID_PITCH_KI,
                              kd=config.PID_PITCH_KD)

        # latest values
        self.target_yaw: float = 0.0
        self.target_pitch: float = 0.0
        self.cmd_yaw: float = 0.0
        self.cmd_pitch: float = 0.0
        self.cmd_roll: float = 0.0

        self._last_pose_t: float = 0.0

    # ── calibration ─────────────────────────────────────────────────────
    def calibrate_zero(self, quat: list):
        self._ref_quat = list(quat)
        self._yaw_ema.reset()
        self._pitch_ema.reset()
        self._yaw_pid.reset()
        self._pitch_pid.reset()
        log.info("Calibration set: ref_quat=%s", self._ref_quat)

    # ── pose update (phone) ─────────────────────────────────────────────
    def update_phone_pose(self, quat: list, pos: list | None = None,
                          t: float | None = None):
        """Compute target yaw/pitch from phone quaternion."""
        self._last_pose_t = t or time.time()

        if self._ref_quat is None:
            self._ref_quat = list(quat)
            log.info("Auto-calibrating ref_quat on first pose")

        rel = relative_quat(self._ref_quat, quat)
        roll_raw, pitch_raw, yaw_raw = quat_to_euler(rel)

        self.target_yaw = self._yaw_ema.update(angle_wrap(yaw_raw))
        self.target_pitch = self._pitch_ema.update(angle_wrap(pitch_raw))

    # ── compute output commands ─────────────────────────────────────────
    def compute(self, cv_yaw: float | None = None,
                cv_pitch: float | None = None,
                now: float | None = None):
        """Produce normalized stick commands [-1, +1].

        If CV measurements are available, run PID (closed-loop).
        Otherwise, map phone orientation directly (open-loop).
        """
        now = now or time.time()

        if cv_yaw is not None and cv_pitch is not None:
            yaw_err = angle_wrap(self.target_yaw - cv_yaw)
            pitch_err = angle_wrap(self.target_pitch - cv_pitch)
            self.cmd_yaw = self._yaw_pid.update(yaw_err, now)
            self.cmd_pitch = self._pitch_pid.update(pitch_err, now)
        else:
            scale = 1.0 / math.pi
            self.cmd_yaw = max(-1.0, min(1.0, self.target_yaw * scale))
            self.cmd_pitch = max(-1.0, min(1.0, self.target_pitch * scale))

        if self.mode == "full":
            self.cmd_roll = 0.0  # placeholder; could map phone roll
        else:
            self.cmd_roll = 0.0

        return self.cmd_yaw, self.cmd_pitch, self.cmd_roll

    # ── UI messages ─────────────────────────────────────────────────────
    def handle_ui(self, msg: dict):
        if "brightness" in msg:
            self.brightness = float(msg["brightness"])
        if "color" in msg:
            self.color = tuple(msg["color"])
        if "mode" in msg:
            self.mode = msg["mode"]
            log.info("Control mode → %s", self.mode)

    # ── safety ──────────────────────────────────────────────────────────
    def kill(self):
        self.armed = False
        self.cmd_yaw = 0.0
        self.cmd_pitch = 0.0
        self.cmd_roll = 0.0
        self._yaw_pid.reset()
        self._pitch_pid.reset()
        log.warning("KILL SWITCH activated — disarmed")

    def arm(self):
        self.armed = True
        log.info("Armed")

    @property
    def flags(self) -> int:
        f = 0
        if self.armed:
            f |= 1
        return f

    @property
    def stale(self) -> bool:
        return (time.time() - self._last_pose_t) > config.FAILSAFE_TIMEOUT
