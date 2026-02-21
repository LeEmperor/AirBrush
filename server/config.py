"""Central configuration — all tunables in one place.

Environment variables prefixed with AIRBRUSH_ override defaults.
"""

import os

def _env(name: str, default):
    v = os.environ.get(f"AIRBRUSH_{name}")
    if v is None:
        return default
    if isinstance(default, bool):
        return v.lower() in ("1", "true", "yes")
    if isinstance(default, int):
        return int(v)
    if isinstance(default, float):
        return float(v)
    return v

# ── networking ──────────────────────────────────────────────────────────────
WS_HOST: str          = _env("WS_HOST", "0.0.0.0")
WS_PORT: int          = _env("WS_PORT", 8765)

ESP_IP: str           = _env("ESP_IP", "192.168.4.1")
ESP_PORT: int         = _env("ESP_PORT", 9002)

PI_IP: str            = _env("PI_IP", "192.168.4.2")
PI_PORT: int          = _env("PI_PORT", 9003)

# ── control ─────────────────────────────────────────────────────────────────
CONTROL_MODE: str     = _env("CONTROL_MODE", "yaw_pitch")   # "yaw_pitch" | "full"
FAILSAFE_TIMEOUT: float = _env("FAILSAFE_TIMEOUT", 0.200)   # seconds
ESP_SEND_HZ: int      = _env("ESP_SEND_HZ", 50)             # command rate to ESP
SMOOTHING_ALPHA: float = _env("SMOOTHING_ALPHA", 0.25)       # EMA filter [0..1]

# PID gains (yaw)
PID_KP: float         = _env("PID_KP", 0.6)
PID_KI: float         = _env("PID_KI", 0.02)
PID_KD: float         = _env("PID_KD", 0.1)
# PID gains (pitch)
PID_PITCH_KP: float   = _env("PID_PITCH_KP", 0.5)
PID_PITCH_KI: float   = _env("PID_PITCH_KI", 0.01)
PID_PITCH_KD: float   = _env("PID_PITCH_KD", 0.08)

# ── CV ──────────────────────────────────────────────────────────────────────
CV_ENABLED: bool      = _env("CV_ENABLED", True)
CAMERA_INDEX: int     = _env("CAMERA_INDEX", 0)
MARKER_ID: int        = _env("MARKER_ID", 42)
MARKER_SIZE_M: float  = _env("MARKER_SIZE_M", 0.10)

# Default camera intrinsics (640×480 webcam estimate).
# Replace with your calibration for real accuracy.
CAMERA_MATRIX = None   # set by calibration loader or left as None for defaults
DIST_COEFFS   = None

# ── LED / light ─────────────────────────────────────────────────────────────
DEFAULT_BRIGHTNESS: float = _env("DEFAULT_BRIGHTNESS", 0.5)

# ── web static files ───────────────────────────────────────────────────────
import pathlib
WEB_DIR: str = str(pathlib.Path(__file__).resolve().parent.parent / "web")

# ── logging ─────────────────────────────────────────────────────────────────
LOG_LEVEL: str = _env("LOG_LEVEL", "INFO")
