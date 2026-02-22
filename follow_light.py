import cv2
import numpy as np
import time

cap = cv2.VideoCapture(0)

assert cap.isOpened(), "Cannot open camera or video feed"

fps = 30
prev = 0

alpha = 0.5  # Transparency of the first image
beta = 1 - alpha # Transparency of the second image
gamma = 0        # Scalar added to the result

first_frame = None


last_mean = 0
bg_subtract = cv2.createBackgroundSubtractorMOG2(varThreshold=50, history=10, detectShadows=False)

while cap.isOpened():
    elapsed = time.time() - prev
    ret, frame = cap.read()

    assert ret, "Cannot receive frame"

    if elapsed > 1/fps:
        prev = time.time()

        if ret:

            img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)


            img_blurred = cv2.GaussianBlur(img_gray, (31,31), 10)
            ret_thresh, thresh_bright = cv2.threshold(img_gray, 235, 255, cv2.THRESH_BINARY)

            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11,11))

            mask_eroded = cv2.morphologyEx(thresh_bright, cv2.MORPH_OPEN, kernel)

            fg_mask = bg_subtract.apply(mask_eroded)
            thresh_bright = cv2.bitwise_and(thresh_bright, thresh_bright, mask=fg_mask)

            contours, hierarchy = cv2.findContours(thresh_bright, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)


            min_contour_area = 300
            large_contours = [cnt for cnt in contours if cv2.contourArea(cnt) > min_contour_area]

            frame_out = frame.copy()
            for cnt in large_contours:
                x,y,w,h = cv2.boundingRect(cnt)
                frame_out = cv2.rectangle(frame_out, (x, y), (x + w, y + h), (255, 0, 0), 3)

                # cv2.imwrite(f"frame_test/{prev}.png", frame_out)


            if first_frame is None:
                first_frame = frame
                first_frame_thresh = frame
                blended_image = frame


            x = cv2.bitwise_or(frame, frame, mask=thresh_bright)

            blended_image = cv2.addWeighted(blended_image, 1, x, beta, gamma)

            cv2.imshow("Frame", blended_image)









    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
