"""Overlay drawing for CV debug window."""

import math
import cv2


def draw_hud(frame, pose):
    """Draw a heads-up display with pose data on the frame."""
    h, w = frame.shape[:2]

    # semi-transparent bar at bottom
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, h - 80), (w, h), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)

    if pose is None:
        cv2.putText(frame, "NO MARKER DETECTED", (10, h - 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        return frame

    yaw_d   = math.degrees(pose["yaw"])
    pitch_d = math.degrees(pose["pitch"])
    roll_d  = math.degrees(pose["roll"])
    x, y, z = pose["x"], pose["y"], pose["z"]

    line1 = f"Yaw: {yaw_d:+6.1f}   Pitch: {pitch_d:+6.1f}   Roll: {roll_d:+6.1f}"
    line2 = f"Pos: ({x:+.3f}, {y:+.3f}, {z:+.3f}) m"

    cv2.putText(frame, line1, (10, h - 50),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 0), 1)
    cv2.putText(frame, line2, (10, h - 25),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 0), 1)

    # crosshair at frame center
    cx, cy = w // 2, h // 2
    cv2.line(frame, (cx - 20, cy), (cx + 20, cy), (255, 255, 0), 1)
    cv2.line(frame, (cx, cy - 20), (cx, cy + 20), (255, 255, 0), 1)

    return frame
