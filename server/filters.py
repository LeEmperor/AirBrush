"""Smoothing filters and PID controller."""

from __future__ import annotations
import time
import math


class EMAFilter:
    """Exponential moving average — works on scalars or lists."""

    def __init__(self, alpha: float = 0.3):
        self.alpha = alpha
        self._val = None

    def update(self, raw):
        if self._val is None:
            self._val = raw if not isinstance(raw, list) else list(raw)
            return self._val
        a = self.alpha
        if isinstance(raw, (list, tuple)):
            self._val = [a * r + (1 - a) * s for r, s in zip(raw, self._val)]
        else:
            self._val = a * raw + (1 - a) * self._val
        return self._val

    def reset(self):
        self._val = None

    @property
    def value(self):
        return self._val


class PID:
    """Discrete PID with anti-windup clamp and derivative-on-measurement."""

    def __init__(self, kp=1.0, ki=0.0, kd=0.0, out_min=-1.0, out_max=1.0,
                 integral_max=0.5):
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.out_min = out_min
        self.out_max = out_max
        self.integral_max = integral_max
        self._integral = 0.0
        self._prev_error = 0.0
        self._prev_time: float | None = None

    def update(self, error: float, now: float | None = None) -> float:
        now = now or time.monotonic()
        if self._prev_time is None:
            dt = 0.02
        else:
            dt = max(now - self._prev_time, 1e-6)
        self._prev_time = now

        self._integral += error * dt
        self._integral = max(-self.integral_max,
                             min(self.integral_max, self._integral))

        derivative = (error - self._prev_error) / dt
        self._prev_error = error

        out = self.kp * error + self.ki * self._integral + self.kd * derivative
        return max(self.out_min, min(self.out_max, out))

    def reset(self):
        self._integral = 0.0
        self._prev_error = 0.0
        self._prev_time = None


# ── quaternion / euler helpers ──────────────────────────────────────────────

def quat_to_euler(q):
    """Convert [x, y, z, w] quaternion to (roll, pitch, yaw) in radians."""
    x, y, z, w = q
    sinr_cosp = 2.0 * (w * x + y * z)
    cosr_cosp = 1.0 - 2.0 * (x * x + y * y)
    roll = math.atan2(sinr_cosp, cosr_cosp)

    sinp = 2.0 * (w * y - z * x)
    sinp = max(-1.0, min(1.0, sinp))
    pitch = math.asin(sinp)

    siny_cosp = 2.0 * (w * z + x * y)
    cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
    yaw = math.atan2(siny_cosp, cosy_cosp)

    return roll, pitch, yaw


def euler_to_quat(roll: float, pitch: float, yaw: float):
    """(roll, pitch, yaw) radians -> [x, y, z, w] quaternion."""
    cr, sr = math.cos(roll / 2), math.sin(roll / 2)
    cp, sp = math.cos(pitch / 2), math.sin(pitch / 2)
    cy, sy = math.cos(yaw / 2), math.sin(yaw / 2)
    return [
        sr * cp * cy - cr * sp * sy,
        cr * sp * cy + sr * cp * sy,
        cr * cp * sy - sr * sp * cy,
        cr * cp * cy + sr * sp * sy,
    ]


def quat_normalize(q):
    n = math.sqrt(sum(c * c for c in q))
    if n < 1e-10:
        return [0.0, 0.0, 0.0, 1.0]
    return [c / n for c in q]


def quat_conjugate(q):
    return [-q[0], -q[1], -q[2], q[3]]


def quat_multiply(a, b):
    """Hamilton product: a * b, both [x,y,z,w]."""
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return [
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
        aw * bw - ax * bx - ay * by - az * bz,
    ]


def relative_quat(q_ref, q_cur):
    """Return rotation from ref to cur:  q_rel = conj(ref) * cur."""
    return quat_normalize(quat_multiply(quat_conjugate(q_ref), q_cur))


def angle_wrap(a: float) -> float:
    """Wrap angle to [-pi, pi]."""
    return (a + math.pi) % (2 * math.pi) - math.pi
