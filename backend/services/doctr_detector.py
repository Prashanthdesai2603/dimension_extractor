import cv2
import os
import re
import sys
import numpy as np
from unittest.mock import MagicMock

# Mock weasyprint to avoid OSError on Windows (requires GTK+)
sys.modules["weasyprint"] = MagicMock()

from doctr.io import DocumentFile
from doctr.models import ocr_predictor
from pdf2image import convert_from_path
from .dimension_detector import is_dimension

# Load docTR model
# Standard predictor is stable; we will handle rotation via a two-pass approach
model = ocr_predictor(pretrained=True)

def expand_box(box, img_shape):
    """Step 3: Expand bounding box to ensure full text capture"""
    x = box["x"]
    y = box["y"]
    w = box["width"]
    h = box["height"]
    img_h, img_w = img_shape[:2]

    # Expand by 20% on each side
    new_x = max(0, x - int(w * 0.2))
    new_y = max(0, y - int(h * 0.2))
    new_w = min(img_w - new_x, w + int(w * 0.4))
    new_h = min(img_h - new_y, h + int(h * 0.4))

    return {
        "x": int(new_x),
        "y": int(new_y),
        "width": int(new_w),
        "height": int(new_h)
    }

def detect_dimension_boxes(pdf_path):
    """Step 2: Detect dimension regions using docTR with two-pass logic for rotation"""
    print(f"\n>>> [DOCTR] Loading PDF: {pdf_path}")
    pages = convert_from_path(pdf_path, dpi=300)
    if not pages:
        print(">>> [ERROR] Could not convert PDF to images.")
        return []

    # Process first page
    temp_image = "temp_page_doctr.jpg"
    pages[0].save(temp_image, "JPEG")
    
    cv_img = cv2.imread(temp_image)
    if cv_img is None:
        print(">>> [ERROR] Could not read temp image for docTR.")
        return []
    img_h, img_w = cv_img.shape[:2]

    all_boxes = []

    def process_pass(image_path, is_rotated=False):
        doc = DocumentFile.from_images(image_path)
        result = model(doc)
        pass_boxes = []
        
        for page in result.pages:
            p_h, p_w = page.dimensions
            for block in page.blocks:
                for line in block.lines:
                    words = [w.value for w in line.words]
                    text = " ".join(words)
                    if is_dimension(text):
                        geom = line.geometry
                        # Extract bbox
                        if len(geom) == 4:
                            xs, ys = [p[0] for p in geom], [p[1] for p in geom]
                            x1, y1, x2, y2 = min(xs), min(ys), max(xs), max(ys)
                        else:
                            x1, y1, x2, y2 = geom[0][0], geom[0][1], geom[1][0], geom[1][1]
                        
                        # Map to pixels
                        px1, py1, px2, py2 = x1*p_w, y1*p_h, x2*p_w, y2*p_h
                        
                        if is_rotated:
                            # Map back from 90 CW: x=new_y, y=H-new_x
                            # new_x1, new_y1, new_x2, new_y2 = px1, py1, px2, py2
                            # H is the width of the original image (which is the height of rotated image)
                            orig_x1 = py1
                            orig_y1 = img_h - px2
                            orig_x2 = py2
                            orig_y2 = img_h - px1
                            pass_boxes.append({
                                "x": int(orig_x1), "y": int(orig_y1),
                                "width": int(orig_x2 - orig_x1), "height": int(orig_y2 - orig_y1),
                                "text": text, "vertical": True
                            })
                        else:
                            pass_boxes.append({
                                "x": int(px1), "y": int(py1),
                                "width": int(px2 - px1), "height": int(py2 - py1),
                                "text": text, "vertical": False
                            })
        return pass_boxes

    # Pass 1: Original
    print(">>> [DOCTR] Pass 1: Horizontal detection...")
    all_boxes.extend(process_pass(temp_image, is_rotated=False))

    # Pass 2: Rotated 90 CW (to detect vertical text as horizontal)
    print(">>> [DOCTR] Pass 2: Vertical detection (90 deg rotated)...")
    img_90 = cv2.rotate(cv_img, cv2.ROTATE_90_CLOCKWISE)
    temp_90 = "temp_page_90.jpg"
    cv2.imwrite(temp_90, img_90)
    all_boxes.extend(process_pass(temp_90, is_rotated=True))

    # Step 3: Expand and cleanup
    final_boxes = []
    for box in all_boxes:
        expanded = expand_box(box, cv_img.shape)
        expanded["text"] = box["text"]
        expanded["vertical"] = box["vertical"]
        final_boxes.append(expanded)

    print(f">>> [DOCTR] Total detected candidates: {len(final_boxes)}")
    
    # Cleanup
    for f in [temp_image, temp_90]:
        if os.path.exists(f): os.remove(f)

    return final_boxes
