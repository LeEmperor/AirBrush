import cv2
import numpy as np
from matplotlib import pyplot as plt

cap = cv2.VideoCapture(0)
bg_subtract = cv2.createBackgroundSubtractorMOG2(varThreshold=75, history=1, detectShadows=False)
last_mean = 0

if not cap.isOpened():
    raise IOError("Cannot open video feed")

while cap.isOpened():
    # Get frame by frame capture
    ret, frame = cap.read()

    if ret:
        img_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        fg_mask = bg_subtract.apply(img_gray)
        img_final = cv2.bitwise_and(frame, frame, mask=fg_mask)

        contours, hierarchy = cv2.findContours(fg_mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        frame_ct = cv2.drawContours(frame, contours, -1, (0, 0, 255), 3)

        cv2.imshow("frame", frame_ct)


        result = np.abs(np.mean(img_gray) - last_mean)
        last_mean = np.mean(img_gray)



    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()