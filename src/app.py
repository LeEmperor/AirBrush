import asyncio
import json
import urllib.parse
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import websockets
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

HOST = "dhcp-10-31-152-86.dyn.MIT.EDU"
PORT = 8081

SENSORS = [
    "android.sensor.accelerometer",
    "android.sensor.gyroscope",
    # "android.sensor.rotation_vector",
]

def build_uri(host: str, port: int, sensors: List[str]) -> str:
    base = f"ws://{host}:{port}/sensors/connect?types="
    types_json = json.dumps(sensors)
    return base + urllib.parse.quote(types_json, safe="")

@dataclass
class SensorStreamManager:
    host: str
    port: int
    sensors: List[str]

    stop_event: asyncio.Event = field(default_factory=asyncio.Event)
    task: Optional[asyncio.Task] = None

    # Each client gets its own asyncio.Queue of JSON strings
    clients: Dict[int, asyncio.Queue[str]] = field(default_factory=dict)
    clients_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    next_client_id: int = 1

    running_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    is_running: bool = False

    async def start(self) -> None:
        """Start background WS reader (idempotent)."""
        async with self.running_lock:
            if self.is_running and self.task and not self.task.done():
                return
            self.is_running = True

        self.stop_event.clear()
        self.task = asyncio.create_task(self._ws_reader())

    async def stop(self) -> None:
        """Stop background WS reader and notify clients."""
        async with self.running_lock:
            if not self.is_running:
                return
            self.is_running = False

        self.stop_event.set()
        await self._broadcast(json.dumps({"type": "server", "event": "stopped"}))

        # also cancel the task if it's still around
        if self.task and not self.task.done():
            self.task.cancel()

    async def add_client(self) -> int:
        q: asyncio.Queue[str] = asyncio.Queue(maxsize=200)
        async with self.clients_lock:
            cid = self.next_client_id
            self.next_client_id += 1
            self.clients[cid] = q
        return cid

    async def remove_client(self, cid: int) -> None:
        async with self.clients_lock:
            self.clients.pop(cid, None)

    async def get_client_queue(self, cid: int) -> asyncio.Queue[str]:
        async with self.clients_lock:
            return self.clients[cid]

    async def _broadcast(self, msg: str) -> None:
        """Broadcast to all clients; drop if a client is too slow."""
        async with self.clients_lock:
            for q in self.clients.values():
                try:
                    q.put_nowait(msg)
                except asyncio.QueueFull:
                    # drop message for slow consumers
                    pass

    async def _ws_reader(self) -> None:
        uri = build_uri(self.host, self.port, self.sensors)
        backoff = 0.5

        while not self.stop_event.is_set():
            try:
                async with websockets.connect(uri) as ws:
                    await self._broadcast(json.dumps({"type": "server", "event": "connected"}))
                    backoff = 0.5

                    async for message in ws:
                        if self.stop_event.is_set():
                            break

                        if isinstance(message, (bytes, bytearray)):
                            try:
                                message = message.decode("utf-8", errors="replace")
                            except Exception:
                                message = str(message)

                        # Ensure JSON string payload
                        try:
                            json.loads(message)
                            payload = message
                        except json.JSONDecodeError:
                            payload = json.dumps({"type": "unknown", "raw": message})

                        await self._broadcast(payload)

            except asyncio.CancelledError:
                break
            except Exception as e:
                await self._broadcast(json.dumps({"type": "server", "event": "error", "detail": str(e)}))
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 8.0)

        await self._broadcast(json.dumps({"type": "server", "event": "disconnected"}))


app = FastAPI()
manager = SensorStreamManager(HOST, PORT, SENSORS)

@app.on_event("startup")
async def on_startup():
    # optional: don't auto-start; only start when first client connects
    pass

@app.get("/sensors/stream")
async def sensors_stream(request: Request):
    """
    SSE stream of sensor data.
    Starts the SensorServer websocket reader on-demand.
    """
    await manager.start()

    cid = await manager.add_client()
    q = await manager.get_client_queue(cid)

    async def event_generator():
        try:
            # initial status event
            yield {"event": "status", "data": json.dumps({"type": "server", "event": "stream_started"})}

            # keepalive ticker
            keepalive_every = 15.0
            next_keepalive = asyncio.get_event_loop().time() + keepalive_every

            while True:
                # client disconnected?
                if await request.is_disconnected():
                    break

                # manager stopped?
                if manager.stop_event.is_set():
                    yield {"event": "status", "data": json.dumps({"type": "server", "event": "stopped"})}
                    break

                # wait for message or keepalive
                timeout = max(0.0, next_keepalive - asyncio.get_event_loop().time())
                try:
                    msg = await asyncio.wait_for(q.get(), timeout=timeout)
                    yield {"event": "sensor", "data": msg}
                except asyncio.TimeoutError:
                    # SSE comment as keepalive (EventSourceResponse supports raw strings too,
                    # but we can just send a status ping)
                    yield {"event": "status", "data": json.dumps({"type": "server", "event": "keepalive"})}
                    next_keepalive = asyncio.get_event_loop().time() + keepalive_every

        finally:
            await manager.remove_client(cid)

    return EventSourceResponse(event_generator())

@app.post("/turn_off")
async def turn_off():
    await manager.stop()
    return JSONResponse({"ok": True, "status": "stopping"})

@app.post("/turn_on")
async def turn_on():
    await manager.start()
    return JSONResponse({"ok": True, "status": "running"})

@app.get("/status")
async def status():
    async with manager.clients_lock:
        n_clients = len(manager.clients)
    running = manager.is_running and not manager.stop_event.is_set()
    return JSONResponse({
        "running": running,
        "clients": n_clients,
        "sensors": manager.sensors,
        "host": manager.host,
        "port": manager.port,
    })