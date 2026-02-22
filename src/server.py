# server.py
import inspect
import json
import math
import struct
import asyncio
from contextlib import asynccontextmanager
from typing import Any, Callable

import numpy as np
import zmq
import zmq.asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, StreamingResponse


PoseCallback = Callable[[dict[str, Any], WebSocket], Any]

# --- Binary packet formats over ZMQ ---
# 1-byte packet type + uint64 timestamp + payload
# Pose:  b'P' + <Q> + 16 float32 row-major (64 bytes)
# Event: b'E' + <Q> + <c> (1 byte event code)
PKT_TYPE = struct.Struct("<c")
U64 = struct.Struct("<Q")
EVT = struct.Struct("<c")


class ZmqPublisher:
    def __init__(self, bind_addr: str = "tcp://127.0.0.1:5556"):
        self._ctx = zmq.asyncio.Context.instance()
        self._sock = self._ctx.socket(zmq.PUB)
        self._sock.bind(bind_addr)

        # Low-latency tuning
        self._sock.setsockopt(zmq.SNDHWM, 1)
        self._sock.setsockopt(zmq.LINGER, 0)

        # Latest-only: keeps the newest message; older ones may be dropped.
        # NOTE: If you need events to NEVER be dropped, remove CONFLATE here,
        # or use a second PUB socket/port for events.
        self._sock.setsockopt(zmq.CONFLATE, 1)

    async def send(self, payload: bytes) -> None:
        await self._sock.send(payload)

    def close(self) -> None:
        try:
            self._sock.close(linger=0)
        except Exception:
            pass


publisher = ZmqPublisher("tcp://127.0.0.1:5556")


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        yield
    finally:
        publisher.close()


app = FastAPI(lifespan=lifespan)


class PoseWSHandler:
    def __init__(self, *, on_pose: PoseCallback, verbose: bool = True):
        self.on_pose = on_pose
        self.verbose = verbose

    async def handle(self, ws: WebSocket) -> None:
        await ws.accept()
        if self.verbose:
            print("✅ WebSocket connected")

        try:
            while True:
                msg = await ws.receive_text()
                await self._on_message(ws, msg)

        except WebSocketDisconnect:
            if self.verbose:
                print("❌ Phone disconnected")

    async def _on_message(self, ws: WebSocket, msg: str) -> None:
        try:
            data = json.loads(msg)
        except Exception:
            return

        mtype = data.get("type")
        if mtype == "pose":
            await self._call_on_pose(data, ws)
        elif mtype == "event":
            await self._handle_event(data)
        else:
            # ignore hello/heartbeat/bye
            return

    async def _call_on_pose(self, data: dict, ws: WebSocket) -> None:
        try:
            res = self.on_pose(data, ws)
            if inspect.isawaitable(res):
                await res
        except Exception as e:
            print("❌ on_pose error:", repr(e))

    async def _handle_event(self, data: dict) -> None:
        """
        Receives: {"type":"event","data":"launch"|"land", "t_ms":...}
        Publishes binary event packet to ZMQ.
        """
        name = data.get("data")
        t_ms = int(data.get("t_ms") or 0)

        if name == "launch":
            code = b"L"
        elif name == "land":
            code = b"D"
        else:
            code = b"?"  # unknown event

        payload = PKT_TYPE.pack(b"E") + U64.pack(t_ms) + EVT.pack(code)
        await publisher.send(payload)


def quat_to_rotmat_xyzw(qx: float, qy: float, qz: float, qw: float) -> np.ndarray:
    n = math.sqrt(qx*qx + qy*qy + qz*qz + qw*qw)
    if n == 0.0:
        return np.eye(3, dtype=np.float32)

    qx, qy, qz, qw = qx/n, qy/n, qz/n, qw/n
    xx, yy, zz = qx*qx, qy*qy, qz*qz
    xy, xz, yz = qx*qy, qx*qz, qy*qz
    wx, wy, wz = qw*qx, qw*qy, qw*qz

    return np.array([
        [1.0 - 2.0*(yy + zz), 2.0*(xy - wz),       2.0*(xz + wy)],
        [2.0*(xy + wz),       1.0 - 2.0*(xx + zz), 2.0*(yz - wx)],
        [2.0*(xz - wy),       2.0*(yz + wx),       1.0 - 2.0*(xx + yy)],
    ], dtype=np.float32)


def pose_to_T_xyzw(px: float, py: float, pz: float, qx: float, qy: float, qz: float, qw: float) -> np.ndarray:
    R = quat_to_rotmat_xyzw(qx, qy, qz, qw)
    T = np.eye(4, dtype=np.float32)
    T[:3, :3] = R
    T[:3, 3] = (px, py, pz)
    return T


async def transform_to_homogenous_matrix(data: dict[str, Any], ws: WebSocket):
    """
    Receives pose JSON from the phone, publishes binary pose packet to ZMQ.
    """
    p = data.get("pos") or {}
    q = data.get("quat") or {}

    def f(v):
        try:
            return float(v)
        except Exception:
            return None

    qx, qy, qz, qw = f(q.get("x")), f(q.get("y")), f(q.get("z")), f(q.get("w"))
    px, py, pz = f(p.get("x")), f(p.get("y")), f(p.get("z"))
    if None in (qx, qy, qz, qw, px, py, pz):
        return

    t_ms = int(data.get("t_ms") or 0)
    T = pose_to_T_xyzw(px, py, pz, qx, qy, qz, qw)  # 4x4 float32

    # Pose packet: 'P' + t_ms + 16 float32
    payload = PKT_TYPE.pack(b"P") + U64.pack(t_ms) + T.reshape(16).tobytes()
    await publisher.send(payload)


handler = PoseWSHandler(on_pose=transform_to_homogenous_matrix, verbose=False)


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await handler.handle(ws)


app = FastAPI()
latest_frame: bytes | None = None

HTML = """<!DOCTYPE html>
<html>
<body>
<video id="v" autoplay playsinline></video>
<canvas id="c" hidden></canvas>
<script>
const proto = location.protocol === 'https:' ? 'wss' : 'ws';
const ws = new WebSocket(`${proto}://${location.host}/camera`);
const v = document.getElementById('v');
const c = document.getElementById('c');

navigator.mediaDevices.getUserMedia({video: true}).then(s => {
  v.srcObject = s;
  v.onloadedmetadata = () => {
    c.width = v.videoWidth;
    c.height = v.videoHeight;
    setInterval(() => {
      if (ws.readyState !== WebSocket.OPEN) return;
      c.getContext('2d').drawImage(v, 0, 0);
      c.toBlob(b => b.arrayBuffer().then(a => ws.send(a)), 'image/jpeg', 0.8);
    }, 50);
  };
});
</script>
</body>
</html>"""

@app.get("/", response_class=HTMLResponse)
async def index():
    return HTML

@app.websocket("/camera")
async def ws_endpoint(websocket: WebSocket):
    global latest_frame
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_bytes()
            latest_frame = data
            # with open("/tmp/frame.jpg", "wb") as f:
            #     f.write(data)
    except Exception:
        pass

async def mjpeg_stream():
    while True:
        if latest_frame:
            yield b"--f\r\nContent-Type: image/jpeg\r\n\r\n" + latest_frame + b"\r\n"
        await asyncio.sleep(0.033)

@app.get("/stream")
async def stream():
    return StreamingResponse(mjpeg_stream(), media_type="multipart/x-mixed-replace; boundary=f")