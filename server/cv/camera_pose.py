#!/usr/bin/env python3
"""ArUco marker detection and 6-DOF pose estimation.

Detects a specific ArUco marker (default ID 42, DICT_4X4_50), estimates
its pose via solvePnP, and yields smoothed yaw/pitch/roll in world coords.

Run standalone:
    python -m cv.camera_pose
"""

from __future__ import annotations
import logging
import math
import time
from typing import Generator

import cv2
import numpy as np

log = logging.getLogger("cv.pose")

# Default camera intrinsics for a typical 640×480 USB webcam.
# Replace with calibrated values for real accuracy.
DEFAULT_CAMERA_MATRIX = np.array([
    [600, 0,   320],
    [0,   600, 240],
    [0,   0,   1  ],
], dtype=np.float64)
DEFAULT_DIST_COEFFS = np.zeros(5, dtype=np.float64)


def _rotation_matrix_to_euler(R):
    """Extract (roll, pitch, yaw) from a 3×3 rotation matrix (XYZ convention)."""
    sy = math.sqrt(R[0, 0] ** 2 + R[1, 0] ** 2)
    singular = sy < 1e-6
    if not singular:
        roll  = math.atan2(R[2, 1], R[2, 2])
        pitch = math.atan2(-R[2, 0], sy)
        yaw   = math.atan2(R[1, 0], R[0, 0])
    else:
        roll  = math.atan2(-R[1, 2], R[1, 1])
        pitch = math.atan2(-R[2, 0], sy)
        yaw   = 0.0
    return roll, pitch, yaw


class CameraPoseEstimator:
    """Streams 6-DOF pose estimates from a single ArUco marker."""

    def __init__(self, camera_index=0, marker_id=42, marker_size=0.10,
                 camera_matrix=None, dist_coeffs=None,
                 smooth_alpha=0.3, show_window=True):
        self.camera_index = camera_index
        self.marker_id = marker_id
        self.marker_size = marker_size
        self.camera_matrix = (camera_matrix if camera_matrix is not None
                              else DEFAULT_CAMERA_MATRIX)
        self.dist_coeffs = (dist_coeffs if dist_coeffs is not None
                            else DEFAULT_DIST_COEFFS)
        self.smooth_alpha = smooth_alpha
        self.show_window = show_window

        self._aruco_dict = cv2.aruco.getPredefinedDictionary(
            cv2.aruco.DICT_4X4_50)
        self._aruco_params = cv2.aruco.DetectorParameters()
        self._detector = cv2.aruco.ArucoDetector(
            self._aruco_dict, self._aruco_params)

        self._smoothed = None

    def _smooth(self, values: dict) -> dict:
        if self._smoothed is None:
            self._smoothed = dict(values)
            return self._smoothed
        a = self.smooth_alpha
        for k in ("x", "y", "z", "roll", "pitch", "yaw"):
            self._smoothed[k] = a * values[k] + (1 - a) * self._smoothed[k]
        return dict(self._smoothed)

    def estimate_pose(self, frame):
        """Detect marker and estimate pose in a single frame.

        Returns (pose_dict, annotated_frame) or (None, annotated_frame).
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        corners, ids, _ = self._detector.detectMarkers(gray)

        vis = frame.copy()
        if ids is not None:
            cv2.aruco.drawDetectedMarkers(vis, corners, ids)

        if ids is None or self.marker_id not in ids.flatten():
            return None, vis

        idx = list(ids.flatten()).index(self.marker_id)
        marker_corners = corners[idx]

        obj_points = np.array([
            [-self.marker_size / 2,  self.marker_size / 2, 0],
            [ self.marker_size / 2,  self.marker_size / 2, 0],
            [ self.marker_size / 2, -self.marker_size / 2, 0],
            [-self.marker_size / 2, -self.marker_size / 2, 0],
        ], dtype=np.float64)

        success, rvec, tvec = cv2.solvePnP(
            obj_points,
            marker_corners.reshape(4, 2),
            self.camera_matrix,
            self.dist_coeffs,
            flags=cv2.SOLVEPNP_IPPE_SQUARE,
        )

        if not success:
            return None, vis

        R, _ = cv2.Rodrigues(rvec)
        roll, pitch, yaw = _rotation_matrix_to_euler(R)

        raw = {
            "x": float(tvec[0, 0]),
            "y": float(tvec[1, 0]),
            "z": float(tvec[2, 0]),
            "roll": roll,
            "pitch": pitch,
            "yaw": yaw,
            "t": time.time(),
        }

        pose = self._smooth(raw)

        # draw axes overlay
        cv2.drawFrameAxes(vis, self.camera_matrix, self.dist_coeffs,
                          rvec, tvec, self.marker_size * 0.6)

        return pose, vis

    def stream(self) -> Generator[dict, None, None]:
        """Open camera and yield pose dicts continuously."""
        cap = cv2.VideoCapture(self.camera_index)
        if not cap.isOpened():
            log.error("Cannot open camera %d", self.camera_index)
            return

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        log.info("Camera %d opened at %.0f×%.0f",
                 self.camera_index,
                 cap.get(cv2.CAP_PROP_FRAME_WIDTH),
                 cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        fps_t = time.time()
        fps_count = 0

        try:
            while True:
                ok, frame = cap.read()
                if not ok:
                    log.warning("Frame grab failed")
                    time.sleep(0.01)
                    continue

                pose, vis = self.estimate_pose(frame)

                fps_count += 1
                if time.time() - fps_t >= 2.0:
                    fps = fps_count / (time.time() - fps_t)
                    log.info("CV FPS: %.1f  | pose: %s",
                             fps,
                             f"yaw={math.degrees(pose['yaw']):.1f}° "
                             f"pitch={math.degrees(pose['pitch']):.1f}°"
                             if pose else "no marker")
                    fps_count = 0
                    fps_t = time.time()

                if self.show_window:
                    from cv.viz import draw_hud
                    vis = draw_hud(vis, pose)
                    cv2.imshow("AirBrush CV", vis)
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        break

                if pose is not None:
                    yield pose

        finally:
            cap.release()
            if self.show_window:
                cv2.destroyAllWindows()


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))
    import config
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(name)s %(levelname)s %(message)s")

    est = CameraPoseEstimator(
        camera_index=config.CAMERA_INDEX,
        marker_id=config.MARKER_ID,
        marker_size=config.MARKER_SIZE_M,
    )
    for pose in est.stream():
        pass  # pose is logged + shown in window
