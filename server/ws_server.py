"""WebSocket pose server + static file server for the web client.

Uses `websockets` 12–13.x legacy API. Static files are served via the
process_request hook — any non-/ws path gets served from the /web/ directory.
"""

from __future__ import annotations
import asyncio
import json
import logging
import mimetypes
import time
from pathlib import Path
from http import HTTPStatus

import websockets

import config

log = logging.getLogger("ws_server")

# shared state — set by main.py
controller = None   # ControlMapper instance
udp: object = None  # UDPLink instance

# ── static file serving ────────────────────────────────────────────────────

WEB_ROOT = Path(config.WEB_DIR)
MIME_EXTRA = {".js": "application/javascript", ".mjs": "application/javascript"}


async def _process_request(path, request_headers):
    """process_request hook (websockets 12-13 legacy API).

    Receives (path: str, headers).
    Return (HTTPStatus, [(name, value), ...], body_bytes) to send HTTP.
    Return None to proceed with the WebSocket handshake.
    """
    if path.startswith("/ws"):
        return None  # let websockets handle the upgrade

    if path in ("", "/"):
        path = "/index.html"

    fp = (WEB_ROOT / path.lstrip("/")).resolve()
    if not str(fp).startswith(str(WEB_ROOT)):
        return HTTPStatus.FORBIDDEN, [], b"Forbidden"
    if not fp.is_file():
        return HTTPStatus.NOT_FOUND, [], b"Not Found"

    ct = MIME_EXTRA.get(fp.suffix,
                        mimetypes.guess_type(str(fp))[0] or
                        "application/octet-stream")
    body = fp.read_bytes()
    headers = [
        ("Content-Type", ct),
        ("Content-Length", str(len(body))),
        ("Cache-Control", "no-cache"),
    ]
    return HTTPStatus.OK, headers, body


# ── WebSocket handler ──────────────────────────────────────────────────────

class JsonPoseHandler:
    """Handles one WebSocket client (phone)."""

    def __init__(self, ws):
        self.ws = ws
        self._seq = 0

    async def run(self):
        remote = self.ws.remote_address
        log.info("Client connected: %s", remote)
        try:
            async for raw in self.ws:
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    log.warning("Bad JSON from %s", remote)
                    continue
                self._dispatch(msg)
        except websockets.ConnectionClosed:
            pass
        finally:
            log.info("Client disconnected: %s", remote)

    def _dispatch(self, msg: dict):
        mtype = msg.get("type")
        if mtype == "pose":
            self._handle_pose(msg)
        elif mtype == "calibrate_zero":
            self._handle_calibrate(msg)
        elif mtype == "ui":
            self._handle_ui(msg)
        elif mtype == "kill":
            self._handle_kill()
        elif mtype == "arm":
            self._handle_arm()
        elif mtype == "pong":
            pass
        else:
            log.debug("Unknown message type: %s", mtype)

    def _handle_pose(self, msg: dict):
        quat = msg.get("quat")
        pos = msg.get("pos")
        t = msg.get("t", time.time())
        seq = msg.get("seq", 0)
        if quat is None or len(quat) != 4:
            return
        self._seq = seq
        if controller:
            controller.update_phone_pose(quat, pos, t)
        latency_ms = (time.time() - t) * 1000 if t else 0
        log.debug("pose seq=%d  quat=[%.3f,%.3f,%.3f,%.3f]  "
                  "latency=%.1fms",
                  seq, *quat, latency_ms)

    def _handle_calibrate(self, msg: dict):
        if controller is None:
            return
        if controller._ref_quat is None:
            log.info("Calibrate requested but no pose yet — will use next")
            return
        controller.calibrate_zero(
            msg["quat"] if msg.get("quat") else controller._ref_quat
        )

    def _handle_ui(self, msg: dict):
        if controller:
            controller.handle_ui(msg)

    def _handle_kill(self):
        if controller:
            controller.kill()

    def _handle_arm(self):
        if controller:
            controller.arm()


async def _handler(ws, path=None):
    """Top-level handler passed to websockets.serve."""
    h = JsonPoseHandler(ws)
    await h.run()


async def start(host=None, port=None):
    host = host or config.WS_HOST
    port = port or config.WS_PORT

    async with websockets.serve(
        _handler,
        host, port,
        process_request=_process_request,
        ping_interval=5,
        ping_timeout=10,
        max_size=4096,
    ) as server:
        log.info("WS + HTTP server on %s:%d  (web root: %s)",
                 host, port, WEB_ROOT)
        await asyncio.Future()  # run forever
