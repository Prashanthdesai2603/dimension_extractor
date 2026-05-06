import logging
import os
import cv2
import numpy as np
import re
from paddleocr import PaddleOCR

logger = logging.getLogger(__name__)

# Singleton instance to avoid reloading model
_ocr_instance = None

def get_paddle_ocr():
    """
    Initializes and returns the PaddleOCR instance.
    """
    global _ocr_instance
    if _ocr_instance is None:
        try:
            print("\n>>> [INIT] Initializing PaddleOCR (lang='en')...")
            logger.info("[PaddleEngine] Initializing PaddleOCR (lang='en')...")
            # use_angle_cls=True allows detection of rotated text (90, 180, 270 degrees)
            _ocr_instance = PaddleOCR(use_angle_cls=True, lang='en')
            logger.info("[PaddleEngine] PaddleOCR initialized successfully.")
            print(">>> [SUCCESS] PaddleOCR initialized and ready.")
        except Exception as e:
            logger.error(f"[PaddleEngine] Failed to initialize PaddleOCR: {e}")
            raise e
    return _ocr_instance

def run_paddle_ocr(cv_img):
    """
    Runs PaddleOCR on a CV2 image and returns structured tokens.
    Format: [{'text': '...', 'bbox': [x1, y1, x2, y2], 'conf': 0.9}, ...]
    """
    if cv_img is None or cv_img.size == 0:
        return []
    try:
        ocr = get_paddle_ocr()
        # cls=True enables angle classification
        result = ocr.ocr(cv_img, cls=True)
        
        tokens = []
        if not result or not result[0]:
            return []
            
        for line in result[0]:
            # result format: [ [[x1,y1],[x2,y1],[x2,y2],[x1,y2]], ('text', confidence) ]
            coords = line[0]
            text, confidence = line[1]
            
            x_coords = [p[0] for p in coords]
            y_coords = [p[1] for p in coords]
            
            tokens.append({
                'text': text,
                'bbox': [min(x_coords), min(y_coords), max(x_coords), max(y_coords)],
                'confidence': float(confidence)
            })
        return tokens
    except Exception as e:
        logger.error(f"[PaddleEngine] Error during OCR execution: {e}")
        return []

def preprocess_image(img):
    """Step 7: Increase contrast and enhance image for OCR"""
    # Convert to grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Increase contrast using CLAHE
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    
    # Return as BGR for PaddleOCR
    return cv2.cvtColor(enhanced, cv2.COLOR_GRAY2BGR)

def run_multi_pass_ocr(crop_img):
    """Step 8: Multi-pass OCR on original, rotated, and enhanced images"""
    if crop_img is None or crop_img.size == 0:
        return "", 0.0

    passes = []
    
    # Pass 1: Original
    passes.append(crop_img)
    
    # Pass 2: Enhanced Contrast
    passes.append(preprocess_image(crop_img))
    
    # Pass 3: Rotated 90 degrees (for vertical dimensions)
    h, w = crop_img.shape[:2]
    if h > w:
        passes.append(cv2.rotate(crop_img, cv2.ROTATE_90_CLOCKWISE))
        passes.append(cv2.rotate(crop_img, cv2.ROTATE_90_COUNTERCLOCKWISE))

    best_text = ""
    best_conf = 0.0

    for idx, img in enumerate(passes):
        tokens = run_paddle_ocr(img)
        if not tokens:
            continue
            
        text = " ".join([t['text'] for t in tokens])
        conf = sum([t['confidence'] for t in tokens]) / len(tokens)
        
        # Heuristic: Check if text contains digits (higher priority for dimensions)
        has_digit = any(char.isdigit() for char in text)
        
        # Multi-pass logic: Choose the one with highest confidence and presence of digits
        score = conf
        if has_digit:
            score += 0.5 # Boost score for dimension-like text
            
        if score > best_conf:
            best_text = text
            best_conf = score # Note: this is a combined score for selection, not pure confidence

    # Return pure confidence for reporting
    final_conf = best_conf - 0.5 if best_conf > 1.0 else best_conf
    return best_text, final_conf

def extract_text_from_region(cv_img):
    """
    Improved extraction using multi-pass and validation logic.
    """
    text, conf = run_multi_pass_ocr(cv_img)
    
    # Step 10: Validation + Retry
    # If text is too short or missing digits, try a slightly larger crop (handled by caller usually)
    # but here we can at least try one more aggressive enhancement
    if len(text) < 2 or not any(c.isdigit() for c in text):
        # Retry with aggressive thresholding
        gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        thresh_bgr = cv2.cvtColor(thresh, cv2.COLOR_GRAY2BGR)
        t_tokens = run_paddle_ocr(thresh_bgr)
        if t_tokens:
            t_text = " ".join([t['text'] for t in t_tokens])
            t_conf = sum([t['confidence'] for t in t_tokens]) / len(t_tokens)
            if any(c.isdigit() for c in t_text):
                return t_text
                
    return text
