import json
import inspect
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import Any, Awaitable, Callable, Optional


app = FastAPI()

# A callback type that takes in a dictionary of any and a websocket. It can return any
PoseCallback = Callable[[dict[str, Any], WebSocket], Any]

class PoseWSHandler:
    def __init__(
            self,
            *,
            on_pose: PoseCallback,
            max_raw_preview: int = 200,
            verbose: bool = True,
    ):
        """
        Initializes the websocket handler with callback functions
        :param on_pose: The callback function to call when pose data arrives
        :param max_raw_preview: The maximum raw data preview if verbose is set
        :param verbose: A flag determining debug logs or not
        """
        self.on_pose = on_pose
        self.max_raw_preview = max_raw_preview
        self.verbose = verbose

    @staticmethod
    def f3(v):
        """Format float-ish values safely."""
        try:
            return f"{float(v):.3f}"
        except Exception:
            return "NA"

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
        except Exception as e:
            print("WS error:", repr(e))
            try:
                await ws.close()
            except Exception:
                pass

    async def _on_message(self, ws: WebSocket, msg: str) -> None:
        """
        The function that handles messages received
        :param ws: The websocket object
        :param msg: The message received from the websocket
        :return:
        """

        try:
            data = json.loads(msg)
        except Exception:
            if self.verbose:
                print("RAW (non-JSON):", msg[: self.max_raw_preview])
            return

        mtype = data.get("type", "unknown")

        if mtype in ("hello", "heartbeat", "frame"):
            if self.verbose:
                print(f"📨 {mtype} t_ms={data.get('t_ms')} has_pose={data.get('has_pose')}")
            return

        if mtype == "pose":
            # Call user-provided function
            await self._call_on_pose(data, ws)
            return

        if self.verbose:
            print("RAW:", msg[: self.max_raw_preview])

    async def _call_on_pose(self, data: dict, ws: WebSocket) -> None:
        """
        Calls the on_pose callback. Supports sync or async callbacks.
        """
        try:
            result = self.on_pose(data, ws)
            if inspect.isawaitable(result):
                await result
        except Exception as e:
            # Decide your desired behavior here:
            # - swallow errors and keep socket alive
            # - or re-raise to close socket
            print("❌ on_pose error:", repr(e))
            return


# ----------------------------
# Example: define your on_pose
# ----------------------------
async def my_pose_action(data: dict[str, Any], ws: WebSocket):
    p = data.get("pos") or {}
    q = data.get("quat") or {}

    # Do anything you want here: write to DB, update global state, broadcast, etc.
    print(
        f"t={data.get('t_ms')}  "
        f"pos=({PoseWSHandler.f3(p.get('x'))},{PoseWSHandler.f3(p.get('y'))},{PoseWSHandler.f3(p.get('z'))})  "
        f"quat=({PoseWSHandler.f3(q.get('x'))},{PoseWSHandler.f3(q.get('y'))},{PoseWSHandler.f3(q.get('z'))},{PoseWSHandler.f3(q.get('w'))})"
    )

    # Example: send an ack back to the client (optional)
    # await ws.send_text(json.dumps({"type": "ack", "t_ms": data.get("t_ms")}))


handler = PoseWSHandler(on_pose=my_pose_action, verbose=True)

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await handler.handle(ws)
