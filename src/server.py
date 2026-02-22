import asyncio
import inspect
import json
import math
import struct
from contextlib import asynccontextmanager
from typing import Any, Callable

import numpy as np
import zmq
import zmq.asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

PoseCallback = Callable[[dict[str, Any], WebSocket], Any]

# Send: uint64 t_ms + 16 float32 (row-major)
HEAD = struct.Struct("<Q")  # 8 bytes


class ZmqPosePublisher:
    def __init__(self, bind_addr: str = "tcp://127.0.0.1:5556"):
        self._ctx = zmq.asyncio.Context.instance()
        self._sock = self._ctx.socket(zmq.PUB)
        self._sock.bind(bind_addr)

        # Low-latency tuning (optional)
        self._sock.setsockopt(zmq.SNDHWM, 1)
        self._sock.setsockopt(zmq.LINGER, 0)
        self._sock.setsockopt(zmq.CONFLATE, 1)  # keep only latest on PUB socket

    async def publish_pose_bytes(self, payload: bytes) -> None:
        await self._sock.send(payload)

    def close(self) -> None:
        try:
            self._sock.close(linger=0)
        except Exception:
            pass


# Latest-only queue (critical to avoid lag)
pose_q: asyncio.Queue[bytes] = asyncio.Queue(maxsize=1)
publisher = ZmqPosePublisher("tcp://127.0.0.1:5556")


async def pump_queue_to_zmq(stop_evt: asyncio.Event):
    while not stop_evt.is_set():
        try:
            payload = await asyncio.wait_for(pose_q.get(), timeout=0.5)
        except asyncio.TimeoutError:
            continue
        await publisher.publish_pose_bytes(payload)


@asynccontextmanager
async def lifespan(app: FastAPI):
    stop_evt = asyncio.Event()
    task = asyncio.create_task(pump_queue_to_zmq(stop_evt))
    try:
        yield
    finally:
        stop_evt.set()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        publisher.close()


app = FastAPI(lifespan=lifespan)


# ----------------------------
# WebSocket handler
# ----------------------------
class PoseWSHandler:
    def __init__(self, *, on_pose: PoseCallback, max_raw_preview: int = 200, verbose: bool = True):
        self.on_pose = on_pose
        self.max_raw_preview = max_raw_preview
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
            if self.verbose:
                print("RAW (non-JSON):", msg[: self.max_raw_preview])
            return

        if data.get("type") == "pose":
            await self._call_on_pose(data, ws)
            return

    async def _call_on_pose(self, data: dict, ws: WebSocket) -> None:
        try:
            result = self.on_pose(data, ws)
            if inspect.isawaitable(result):
                await result
        except Exception as e:
            print("❌ on_pose error:", repr(e))


def quat_to_rotmat_xyzw(qx: float, qy: float, qz: float, qw: float) -> np.ndarray:
    # Normalize
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
    p = data.get("pos") or {}
    q = data.get("quat") or {}

    # Fast float parsing (avoid extra formatting)
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

    # Build payload: 8-byte timestamp + 64-byte matrix (16 float32)
    payload = HEAD.pack(t_ms) + T.reshape(16).tobytes()
    # publish immediately (no queue)
    await publisher.publish_pose_bytes(payload)


handler = PoseWSHandler(on_pose=transform_to_homogenous_matrix, verbose=False)


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await handler.handle(ws)