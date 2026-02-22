# icp.py
import struct
import zmq
import numpy as np
from dataclasses import dataclass
from enum import Enum, auto
from typing import Callable, Dict, Iterator, Optional

# Wire format matches server.py:
# Pose packet:  b'P' + <Q> + 16 float32 (row-major)
# Event packet: b'E' + <Q> + <c>  (event code: b'L' launch, b'D' land, b'?')

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
    T: np.ndarray  # shape (4,4), float32 row-major


@dataclass(frozen=True, slots=True)
class EventMsg:
    kind: MsgKind
    t_ms: int
    event: EventKind


Msg = PoseMsg | EventMsg


class ICP:
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

        # Optional callbacks (now typed)
        self.on_pose: Optional[Callable[[PoseMsg], None]] = None
        self.on_event: Optional[Callable[[EventMsg], None]] = None

        # Optional per-event handlers
        self.event_handlers: Dict[EventKind, Callable[[EventMsg], None]] = {}

    def close(self):
        if not self._closed:
            try:
                self._sub.close(linger=0)
            except Exception:
                pass
            self._closed = True

    def register_event(self, event: EventKind, fn: Callable[[EventMsg], None]) -> None:
        """Register a handler for a specific event enum."""
        self.event_handlers[event] = fn

    @staticmethod
    def _decode_event_code(code: bytes) -> EventKind:
        if code == b"L":
            return EventKind.LAUNCH
        if code == b"D":
            return EventKind.LAND
        return EventKind.UNKNOWN

    def _parse_pose(self, buf: bytes) -> Optional[PoseMsg]:
        # buf: 'P'(1) + t_ms(8) + 16f(64)
        if len(buf) < 1 + 8 + 64:
            return None

        t_ms = int(U64.unpack_from(buf, 1)[0])
        mat_bytes = memoryview(buf)[1 + 8 : 1 + 8 + 64]

        # small copy so caller can safely keep T beyond next recv()
        T = np.frombuffer(mat_bytes, dtype=np.float32, count=16).reshape(4, 4).copy()

        msg = PoseMsg(kind=MsgKind.POSE, t_ms=t_ms, T=T)
        if self.on_pose:
            self.on_pose(msg)
        return msg

    def _parse_event(self, buf: bytes) -> Optional[EventMsg]:
        # buf: 'E'(1) + t_ms(8) + code(1)
        if len(buf) < 1 + 8 + 1:
            return None

        t_ms = int(U64.unpack_from(buf, 1)[0])
        code = EVT.unpack_from(buf, 1 + 8)[0]  # 1-byte bytes object
        event_kind = self._decode_event_code(code)

        msg = EventMsg(kind=MsgKind.EVENT, t_ms=t_ms, event=event_kind)

        if self.on_event:
            self.on_event(msg)
        h = self.event_handlers.get(event_kind)
        if h:
            h(msg)

        return msg

    def __iter__(self) -> Iterator[Msg]:
        while not self._closed:
            buf = self._sub.recv()
            if not buf:
                continue

            ptype = PKT_TYPE.unpack_from(buf, 0)[0]
            if ptype == b"P":
                msg = self._parse_pose(buf)
                if msg is not None:
                    yield msg
            elif ptype == b"E":
                msg = self._parse_event(buf)
                if msg is not None:
                    yield msg
            else:
                continue

    def recv(self) -> Msg:
        return next(iter(self))

    def run(self, on_pose: Callable[[PoseMsg], None]) -> None:
        self.on_pose = on_pose
        try:
            for _ in self:
                pass
        finally:
            self.close()


if __name__ == "__main__":
    icp = ICP("tcp://127.0.0.1:5556", conflate=True)

    for msg in icp:
        if msg.kind is MsgKind.EVENT:
            pass
            # print("event:", msg.t_ms, msg.event)
        else:
            # pose
            print(msg.t_ms, msg.T)
            pass