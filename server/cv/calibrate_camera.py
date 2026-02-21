#!/usr/bin/env python3
"""Quick camera calibration using a chessboard pattern.

Usage:
    python -m cv.calibrate_camera [--camera 0] [--cols 9] [--rows 6]
                                  [--square 0.025] [--out camera_cal.npz]

Hold a printed chessboard in front of the camera. Press SPACE to capture
a frame (need ~15 good frames from different angles). Press Q when done.
The script computes and saves camera_matrix + dist_coeffs.
"""

from __future__ import annotations
import argparse
import sys

import cv2
import numpy as np


def calibrate(camera_index=0, cols=9, rows=6, square_size=0.025,
              output="camera_cal.npz"):
    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        print(f"Cannot open camera {camera_index}", file=sys.stderr)
        return

    obj_p = np.zeros((rows * cols, 3), np.float32)
    obj_p[:, :2] = np.mgrid[0:cols, 0:rows].T.reshape(-1, 2) * square_size

    obj_points = []
    img_points = []
    img_size = None

    print(f"Calibration: {cols}×{rows} inner corners, square={square_size} m")
    print("SPACE = capture frame | Q = finish and calibrate")

    while True:
        ok, frame = cap.read()
        if not ok:
            continue
        if img_size is None:
            img_size = (frame.shape[1], frame.shape[0])
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        found, corners = cv2.findChessboardCorners(gray, (cols, rows), None)

        vis = frame.copy()
        if found:
            cv2.drawChessboardCorners(vis, (cols, rows), corners, found)
            cv2.putText(vis, f"FOUND  ({len(obj_points)} captured)",
                        (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        else:
            cv2.putText(vis, f"Searching...  ({len(obj_points)} captured)",
                        (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

        cv2.imshow("Calibration", vis)
        key = cv2.waitKey(30) & 0xFF

        if key == ord(' ') and found:
            refined = cv2.cornerSubPix(
                gray, corners, (11, 11), (-1, -1),
                (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_COUNT, 30, 0.001))
            obj_points.append(obj_p)
            img_points.append(refined)
            print(f"  Captured frame {len(obj_points)}")

        elif key == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

    if len(obj_points) < 5:
        print("Not enough frames (need ≥5). Aborting.")
        return

    print(f"Calibrating from {len(obj_points)} frames...")
    ret, mtx, dist, rvecs, tvecs = cv2.calibrateCamera(
        obj_points, img_points, img_size, None, None)

    print(f"RMS reprojection error: {ret:.4f}")
    print(f"Camera matrix:\n{mtx}")
    print(f"Distortion coeffs: {dist.ravel()}")

    np.savez(output, camera_matrix=mtx, dist_coeffs=dist)
    print(f"Saved to {output}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--camera", type=int, default=0)
    ap.add_argument("--cols", type=int, default=9)
    ap.add_argument("--rows", type=int, default=6)
    ap.add_argument("--square", type=float, default=0.025)
    ap.add_argument("--out", default="camera_cal.npz")
    args = ap.parse_args()
    calibrate(args.camera, args.cols, args.rows, args.square, args.out)
