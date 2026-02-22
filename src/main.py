import struct
import zmq
import numpy as np
from typing import Callable, Iterator, Tuple

Pose = Tuple[int, np.ndarray]  # (t_ms, 4x4 matrix)


class ICP:
    def __init__(self, addr: str = "tcp://127.0.0.1:5556", *, conflate: bool = True):
        self.addr = addr
        self._ctx = zmq.Context.instance()
        self._sub = self._ctx.socket(zmq.SUB)

        if conflate:
            self._sub.setsockopt(zmq.CONFLATE, 1)  # latest only
            self._sub.setsockopt(zmq.RCVHWM, 1)

        self._sub.setsockopt(zmq.LINGER, 0)
        self._sub.setsockopt(zmq.SUBSCRIBE, b"")
        self._sub.connect(addr)

        self.HEAD = struct.Struct("<Q")    # uint64
        self.MAT16 = struct.Struct("<16f") # 16 float32

        self._closed = False

    def close(self):
        if not self._closed:
            try:
                self._sub.close(linger=0)
            except Exception:
                pass
            self._closed = True

    def __iter__(self) -> Iterator[Pose]:
        """
        Blocking iterator. Yields (t_ms, T) forever until close() or exception.
        """
        while not self._closed:
            buf = self._sub.recv()  # blocks

            t_ms = self.HEAD.unpack_from(buf, 0)[0]
            # Fast zero-copy view of matrix bytes
            T_flat = self.MAT16.unpack_from(buf, 8)  # 16 floats

            # Convert to 4x4 float32 numpy array (small copy, cheap)
            T = np.array(T_flat, dtype=np.float32).reshape(4, 4)
            yield int(t_ms), T

    def recv(self) -> Pose:
        """
        Convenience: get one pose (blocking).
        """
        return next(iter(self))

    def run(self, on_pose: Callable[[int, np.ndarray], None]) -> None:
        """
        Convenience wrapper: calls on_pose(t_ms, T) for each message.
        """
        try:
            for t_ms, T in self:
                on_pose(t_ms, T)
        finally:
            self.close()


if __name__ == '__main__':
    icp = ICP("tcp://127.0.0.1:5556")

    for t_ms, T in icp:
        # do ICP math here
        # T is 4x4 float32, row-major
        print(t_ms, T[0])