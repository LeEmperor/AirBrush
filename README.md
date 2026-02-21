# AirBrush — Phone-Controlled Drone Light Painting

A MakeMIT hardware art project. Move your phone like a wand to aim a
light-equipped drone in 3-D space. The system streams phone orientation over
WebSocket to a Python server, which maps it to drone yaw / pitch commands sent
over UDP to an ESP32. An optional CV module tracks the drone via an ArUco marker
for closed-loop control.

---

## ⚠ Safety

| Rule | Why |
|------|-----|
| **Remove all propellers** during bench / indoor testing | Spinning props near hands → injury |
| **Wear safety glasses** when props are mounted | Prop fragments are sharp |
| **Keep throttle at 0** for rotation-only demos | We only need yaw / pitch / roll |
| **Test servos / LEDs first** before connecting a real controller | Verify signal range |
| **Use the kill switch** (red button in web UI) to disarm instantly | Emergency stop |
| **Never fly indoors** without a prop guard and spotter | Drift → crash |

---

## Architecture

```
Phone (WebXR / sensors)
  │  WebSocket JSON  (~30-60 Hz)
  ▼
Python Server (laptop / Pi)
  ├─ pose intake + smoothing + calibration
  ├─ CV module (optional) – ArUco 6-DOF tracking
  ├─ control mapping  (phone → yaw/pitch setpoints → RC cmds)
  │
  ├──► UDP  ──► ESP32  ──► PPM / servo / LED
  └──► UDP  ──► Raspberry Pi  ──► LED strip / gimbal
```

---

## Quick Start

### 1. Server

```bash
cd server
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python main.py          # default: 0.0.0.0:8765
```

The server hosts the web client at `http://<your-ip>:8765/`.

### 2. Phone

Open `http://<server-ip>:8765/` on your Android phone (same Wi-Fi).
- Tap **Connect** to open the WebSocket.
- Tap **Calibrate Zero** to set the current orientation as the reference.
- Move the phone; you should see pose data logged in the server console.

> **WebXR note:** WebXR requires HTTPS or `localhost`. For LAN testing use the
> DeviceOrientation fallback (works over plain HTTP on most Android browsers).
> On iOS 13+ you must handle the permission prompt — the UI does this automatically.

### 3. ESP32 (bench test)

Flash with PlatformIO:

```bash
cd esp
# Edit src/main.cpp → set your Wi-Fi SSID/password & server IP
pio run -t upload -e esp32
pio device monitor
```

**Wiring for bench test (ESP32):**

| ESP32 Pin | Connection | Purpose |
|-----------|------------|---------|
| GPIO 18   | Servo signal (orange wire) | Yaw test servo |
| GPIO 19   | Servo signal | Pitch test servo |
| GPIO 16   | NeoPixel data in | LED strip (WS2812) |
| GND       | Servo GND + LED GND | Common ground |
| 5 V / VIN | Servo VCC + LED VCC | Power (use external supply for servos) |

### 4. CV Module

Requires a USB camera and a printed ArUco marker (ID 42, DICT_4X4_50,
recommended ≥ 10 cm side). Attach the marker to the drone.

```bash
cd server
python -m cv.camera_pose          # opens camera, detects marker, shows overlay
```

To calibrate your camera (optional but improves accuracy):

```bash
python -m cv.calibrate_camera     # prints a checkerboard, take ~15 photos
```

### 5. Raspberry Pi LED Service (optional)

```bash
cd pi
pip install -r requirements.txt
python light_server.py            # listens on UDP 9003
```

---

## Configuration

All tunables live in `server/config.py`. Key knobs:

| Variable | Default | Meaning |
|----------|---------|---------|
| `WS_HOST` | `0.0.0.0` | WebSocket bind address |
| `WS_PORT` | `8765` | WebSocket / HTTP port |
| `ESP_IP` | `192.168.4.1` | ESP32 IP on LAN |
| `ESP_PORT` | `9002` | UDP port for ESP commands |
| `PI_IP` | `192.168.4.2` | Raspberry Pi IP |
| `PI_PORT` | `9003` | UDP port for Pi LED commands |
| `CV_ENABLED` | `True` | Enable camera tracking |
| `CAMERA_INDEX` | `0` | OpenCV camera device index |
| `MARKER_SIZE_M` | `0.10` | ArUco marker side length (meters) |
| `CONTROL_MODE` | `"yaw_pitch"` | `"yaw_pitch"` or `"full"` |
| `FAILSAFE_TIMEOUT` | `0.2` | Seconds before failsafe (server + ESP) |

Environment variables override config:

```bash
export AIRBRUSH_ESP_IP=10.0.0.50
export AIRBRUSH_WS_PORT=9000
```

---

## Message Formats

### Phone → Server (WebSocket JSON)

```json
{ "type": "pose", "t": 1730000000.123, "seq": 42,
  "pos": [0.1, 1.5, -0.3], "quat": [0.0, 0.1, 0.0, 0.99], "ref": "local" }
{ "type": "calibrate_zero" }
{ "type": "ui", "brightness": 0.6, "mode": "yaw_pitch" }
{ "type": "kill" }
```

### Server → ESP (UDP JSON v1)

```json
{ "t": 1730000000.456, "seq": 1001,
  "yaw": -0.12, "pitch": 0.05, "roll": 0.0, "throttle": 0.0,
  "aux1": 0.7, "flags": 1 }
```

`flags`: bit 0 = armed, bit 1 = failsafe active.

### Server → Pi (UDP JSON)

```json
{ "brightness": 0.6, "color": [255, 180, 120], "pan": 0.1, "tilt": -0.2 }
```

---

## Coordinate Frames

| Frame | Convention |
|-------|-----------|
| **Phone** | WebXR / DeviceOrientation: X-right, Y-up, Z-back-toward-user |
| **World** | Set at calibration. Forward = phone forward at zero moment |
| **Camera** | OpenCV: X-right, Y-down, Z-forward (into scene) |
| **Drone** | NED-ish: yaw = rotation about vertical, pitch = nose up/down |

Quaternion convention everywhere: **[x, y, z, w]** (Hamilton, matching WebXR
`XRRigidTransform.orientation`).

---

## Dependencies

| Component | Package | Why |
|-----------|---------|-----|
| Server | `websockets` | Lightweight async WebSocket server; stdlib has no WS server |
| Server | `numpy` | Fast quaternion / matrix math for pose processing |
| Server | `opencv-contrib-python` | ArUco marker detection + camera calibration (contrib includes `cv2.aruco`) |
| ESP | PlatformIO + Arduino | Standard ESP32 toolchain |
| ESP | `Adafruit_NeoPixel` | WS2812 LED control library |
| ESP | `ESP32Servo` | Servo PWM on ESP32 (ledc-based) |
| Pi | `rpi-lgpio` | GPIO PWM for LED on Raspberry Pi (modern replacement for RPi.GPIO) |

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Phone sensors don't work | Must be HTTPS or localhost for WebXR. DeviceOrientation works on HTTP for Android Chrome. iOS Safari requires user gesture + permission. |
| WebSocket won't connect | Check firewall. Ensure phone and server on same Wi-Fi. Try `ws://<ip>:8765/ws`. |
| ESP not receiving packets | Verify `ESP_IP` in config matches ESP's actual IP. Check `pio device monitor` for Wi-Fi status. |
| ArUco not detected | Print marker larger (≥ 10 cm). Ensure good lighting. Check `MARKER_SIZE_M` matches actual print. |
| Servo jitters | Add a capacitor (100 µF) across servo power. Use external 5 V supply, not USB. |
| High latency | Reduce `POSE_SEND_INTERVAL` in web client. Use UDP (not TCP) for ESP link. |

---

## License

MIT — built for MakeMIT 2026.
