from model_loader import get_paddle_ocr
import cv2
import numpy as np

# initialize OCR using the common loader
ocr = get_paddle_ocr()

# load test image
img_path = "test_image.png"   # use any cropped dimension image
result = ocr.ocr(img_path)

# print results
for line in result:
    for word in line:            
        print(word[1][0])