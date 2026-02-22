import struct
import time
import threading
import zmq
import numpy as np
from dataclasses import dataclass
from enum import Enum, auto
from typing import Callable, Dict, Iterator, Optional

PKT_TYPE = struct.Struct("<c")
U64 = struct.Struct("<Q")
EVT = struct.Struct("<c")


class MsgKind(Enum):
    POSE = auto()
    EVENT = auto()


class EventKind(Enum):
    LAUNCH = auto()
    LAND = auto()
    UNKNOWN = auto()


@dataclass(frozen=True, slots=True)
class PoseMsg:
    kind: MsgKind
    t_ms: int
    T: np.ndarray  # (4,4) float32


@dataclass(frozen=True, slots=True)
class EventMsg:
    kind: MsgKind
    t_ms: int
    event: EventKind


Msg = PoseMsg | EventMsg


class IPC:
    def __init__(self, addr: str = "tcp://127.0.0.1:5556", *, conflate: bool = True):
        self.addr = addr
        self._ctx = zmq.Context.instance()
        self._sub = self._ctx.socket(zmq.SUB)

        if conflate:
            self._sub.setsockopt(zmq.CONFLATE, 1)
            self._sub.setsockopt(zmq.RCVHWM, 1)

        self._sub.setsockopt(zmq.LINGER, 0)
        self._sub.setsockopt(zmq.SUBSCRIBE, b"")
        self._sub.connect(addr)

        self._closed = False

        self.on_pose: Optional[Callable[[PoseMsg], None]] = None
        self.on_event: Optional[Callable[[EventMsg], None]] = None
        self.event_handlers: Dict[EventKind, Callable[[EventMsg], None]] = {}

        self.latest_pose: Optional[PoseMsg] = None
        self.latest_event: Optional[EventMsg] = None

        # ✅ track arrival times (monotonic clock)
        self._last_pose_rx_s: float = 0.0
        self._last_event_rx_s: float = 0.0

        self._lock = threading.Lock()

        self._thread: Optional[threading.Thread] = None
        self._stop_flag = threading.Event()

    def close(self):
        self._stop_flag.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)

        if not self._closed:
            try:
                self._sub.close(linger=0)
            except Exception:
                pass
            self._closed = True

    def register_event(self, event: EventKind, fn: Callable[[EventMsg], None]) -> None:
        self.event_handlers[event] = fn

    @staticmethod
    def _decode_event_code(code: bytes) -> EventKind:
        if code == b"L":
            return EventKind.LAUNCH
        if code == b"D":
            return EventKind.LAND
        return EventKind.UNKNOWN

    def _parse_pose(self, buf: bytes) -> Optional[PoseMsg]:
        if len(buf) < 1 + 8 + 64:
            return None
        t_ms = int(U64.unpack_from(buf, 1)[0])
        mat_bytes = memoryview(buf)[1 + 8: 1 + 8 + 64]
        T = np.frombuffer(mat_bytes, dtype=np.float32, count=16).reshape(4, 4).copy()
        msg = PoseMsg(kind=MsgKind.POSE, t_ms=t_ms, T=T)

        now = time.monotonic()
        with self._lock:
            self.latest_pose = msg
            self._last_pose_rx_s = now

        if self.on_pose:
            self.on_pose(msg)
        return msg

    def _parse_event(self, buf: bytes) -> Optional[EventMsg]:
        if len(buf) < 1 + 8 + 1:
            return None
        t_ms = int(U64.unpack_from(buf, 1)[0])
        code = EVT.unpack_from(buf, 1 + 8)[0]
        event_kind = self._decode_event_code(code)
        msg = EventMsg(kind=MsgKind.EVENT, t_ms=t_ms, event=event_kind)

        now = time.monotonic()
        with self._lock:
            self.latest_event = msg
            self._last_event_rx_s = now

        if self.on_event:
            self.on_event(msg)
        h = self.event_handlers.get(event_kind)
        if h:
            h(msg)
        return msg

    def _parse_any(self, buf: bytes) -> Optional[Msg]:
        if not buf:
            return None
        ptype = PKT_TYPE.unpack_from(buf, 0)[0]
        if ptype == b"P":
            return self._parse_pose(buf)
        if ptype == b"E":
            return self._parse_event(buf)
        return None

    def __iter__(self) -> Iterator[Msg]:
        while not self._closed:
            buf = self._sub.recv()
            msg = self._parse_any(buf)
            if msg is not None:
                yield msg

    def recv(self, timeout_ms: Optional[int] = None) -> Optional[Msg]:
        if timeout_ms is None:
            buf = self._sub.recv()
            return self._parse_any(buf)

        poller = zmq.Poller()
        poller.register(self._sub, zmq.POLLIN)
        events = dict(poller.poll(timeout_ms))
        if self._sub not in events:
            return None
        buf = self._sub.recv(zmq.NOBLOCK)
        return self._parse_any(buf)

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_flag.clear()

        def loop():
            while not self._stop_flag.is_set() and not self._closed:
                _ = self.recv(timeout_ms=200)

        self._thread = threading.Thread(target=loop, daemon=True)
        self._thread.start()

    # ✅ "no data" after stop: return None if stale
    def get_latest_pose(self, *, max_age_ms: int = 200) -> Optional[PoseMsg]:
        """
        Returns latest pose only if it was received within max_age_ms.
        If Stop is pressed and stream halts, this becomes None quickly.
        """
        now = time.monotonic()
        with self._lock:
            lp = self.latest_pose
            age_ms = (now - self._last_pose_rx_s) * 1000.0
        if lp is None:
            return None
        return lp if age_ms <= max_age_ms else None

    def get_latest_translation(self, *, max_age_ms: int = 200) -> Optional[tuple[float, float, float]]:
        lp = self.get_latest_pose(max_age_ms=max_age_ms)
        if lp is None:
            return None
        T = lp.T
        return float(T[0, 3]), float(T[1, 3]), float(T[2, 3])

    def is_stream_alive(self, *, max_age_ms: int = 500) -> bool:
        now = time.monotonic()
        with self._lock:
            last = self._last_pose_rx_s
        return last > 0.0 and ((now - last) * 1000.0) <= max_age_ms


if __name__ == "__main__":
    icp = ICP("tcp://127.0.0.1:5556", conflate=True)
    icp.start()

    while True:
        pose = icp.get_latest_pose(max_age_ms=200)  # ✅ goes None shortly after Stop
        if pose:
            print("pose", pose.t_ms, pose.T[0, :])
        time.sleep(0.05)