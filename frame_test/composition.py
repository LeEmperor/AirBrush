import cv2
import os

img1 = cv2.imread('frame_test/1.png')


# Ensure images are the same size if blending entirely
# For blending a portion, use NumPy slicing (see source)

alpha = 0.2  # Transparency of the first image
beta = 1 - alpha # Transparency of the second image
gamma = 0        # Scalar added to the result

blended_image = cv2.addWeighted(img1, alpha, img1, beta, gamma)

for i, j in enumerate(os.listdir("frame_test/")):
    print(j)
    if ".png" in j:
        j = cv2.imread(f"frame_test/{j}")
        blended_image = cv2.addWeighted(j, alpha, blended_image, beta, gamma)

cv2.imwrite("frame_test/blended_image.png", blended_image)