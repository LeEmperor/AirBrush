import cv2
import math
import numpy as np
from controller import ControllerInterface
from src.ipc import IPC

cap = cv2.VideoCapture(0, cv2.CAP_DSHOW) # Windows specific

def remap(v, low, high):
  return max(min(int((v - low) / (high - low) * 255), 255), 0)

# 0cm initial height, 40x40px
# each 2x multiple of size is halving the 50cm distance

state = dict(
    heading = 0, # starting rotated 90deg S of E
    pos = (0, 0, 0)
)

controller = ControllerInterface('COM14', 115200)
controller.start()

ipc = IPC()
ipc.start()

POSE_MAX_AGE_MS = 200  # if pose older than this, treat as absent


while True:
    ret, frame = cap.read()

    if not ret: 
        print("Failed to grab frame.")
        break

    frame = frame[84+35:434-35, 128+35:478-35, :]

    frame_h, frame_w = frame.shape[:2]

    frame_y = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    frame_y_blurred = cv2.GaussianBlur(frame_y, (3, 3), 0)

    frame_show = np.copy(frame)

    #frame_thresh = cv2.adaptiveThreshold(frame_y, 0xff, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 0)
    ret, frame_thresh = cv2.threshold(frame_y_blurred, 200, 0xff, cv2.THRESH_BINARY)
    frame_thresh = ~frame_thresh
    #kernel = np.ones((5, 5), dtype=np.uint8)
    #frame_thresh = cv2.morphologyEx(frame_thresh, cv2.MORPH_CLOSE, kernel)
    
    contours, _ = cv2.findContours(frame_thresh, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

    best_quad = None

    for i, cnt in enumerate(contours):
        x, y, w, h = cv2.boundingRect(cnt)

        # skip contours on edges
        if x <= 0 or y <= 0 and x + w >= frame_w and y + h >= frame_h:
            continue

        area = cv2.contourArea(cnt)

        if area < 15: continue

        min_rect = cv2.minAreaRect(cnt)
        _, (min_rect_w, min_rect_h), _ = min_rect

        if abs(min_rect_h / min_rect_w - 1.0) > 0.3: continue

        quad = dict(
            cnt=cnt,
            area=area,
            min_rect=min_rect
        )

        if best_quad is None or best_quad["area"] < area:
            best_quad = quad
    
    if best_quad is not None:
        (x, y), (w, h), angle = best_quad["min_rect"]
        angle = np.radians(angle)

        # find closest angle to state (out of 90deg multiples)
        cand_heading = (np.arange(4) * (np.pi*0.5) + angle + np.pi) % (2 * np.pi) - np.pi
        err = np.abs((cand_heading - state["heading"] + np.pi) % (2 * np.pi) - np.pi)
        state["heading"] = cand_heading[np.argmin(err)]

        # calculate 3d position
        wavg = (w + h) * 0.5
        pos_z = (wavg - 40) / 40 * 0.5
        pos_x = (x - frame_w // 2) * pos_z * 0.05
        pos_y = (y - frame_h // 2) * pos_z * 0.05
        pos_x *= -1
        pos_y *= -1

        t = ipc.get_latest_translation(max_age_ms=POSE_MAX_AGE_MS)
        if t is not None:
            tx, ty, tz = t
            pos_x += tx
            pos_y += ty
            pos_z += tz
        else:
            tx = ty = tz = 0.0

        yaw = state["heading"]
        pos = pos_x, pos_y, pos_z
        # print("%0.2f %0.2f %0.2f" % pos)
        rot = np.array([[np.cos(yaw),np.sin(yaw)],[-np.sin(yaw), np.cos(yaw)]])
        pos_2d = rot @ np.array([pos_x, pos_y]) 

        controls = [remap(pos_2d[1], -0.75, 0.75), remap(-pos_2d[0],-0.75, 0.75), remap(-pos_z, -0.75, 0.75), remap(yaw, -math.pi/2, math.pi/2)]
        controller.control(controls)
        print("Controls:", controls)

        box = cv2.boxPoints(best_quad["min_rect"])
        box = np.int32(box)

        pt1 = int(x), int(y)
        pt2 = int(x+np.cos(state["heading"])*20), int(y+np.sin(state["heading"])*20)

        cv2.drawContours(frame_show, [box], 0, (0,0,255), 2)
        cv2.line(frame_show, pt1, pt2, (0, 255, 0), 2)





    #is_bright = frame > 200

    cv2.imshow("frame_thresh", frame_thresh)
    cv2.imshow("frame", frame_show)

    cv2.waitKey(1)


