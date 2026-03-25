import numpy as np
import logging
import cv2
from .model_loader import get_paddle_ocr

logger = logging.getLogger(__name__)

def extract_text_from_region(image_crop, orientation_hint=None):
    """
    Extract text from an image crop using PaddleOCR with multi-rotation testing.
    orientation_hint: 'horizontal' (0, 180) or 'vertical' (90, 270).
    """
    if image_crop is None or image_crop.size == 0:
        return "", 0.0

    from .dimension_detector import is_dimension, get_dimension_match

    try:
        ocr = get_paddle_ocr()
        if ocr is None:
            return "", 0.0

        best_text = ""
        best_conf = 0.0
        is_best_dim = False
        
        # We test all 4 orientations to avoid "damaging" table values 
        # but we prioritize the hint-supported ones.
        rotations = [0, 90, 180, 270]
        
        for angle in rotations:
            # Check if this angle matches the hint
            is_hinted = False
            if orientation_hint == 'horizontal' and angle in [0, 180]:
                is_hinted = True
            elif orientation_hint == 'vertical' and angle in [90, 270]:
                is_hinted = True

            # Rotate image
            if angle == 0:
                rotated = image_crop
            elif angle == 90:
                rotated = cv2.rotate(image_crop, cv2.ROTATE_90_CLOCKWISE)
            elif angle == 180:
                rotated = cv2.rotate(image_crop, cv2.ROTATE_180)
            elif angle == 270:
                rotated = cv2.rotate(image_crop, cv2.ROTATE_90_COUNTERCLOCKWISE)
            
            # OCR with classification
            result = ocr.ocr(rotated, cls=True)
            
            if not result or not result[0]:
                continue
                
            # Join all text blocks in this rotation with spaces to handle fragmented OCR
            full_rotation_text = " ".join([line[1][0] for line in result[0]]).strip()
            # Calculate average confidence for the whole block
            avg_conf = sum([line[1][1] for line in result[0]]) / len(result[0])
            
            # Apply hint boost
            effective_conf = avg_conf * 1.5 if is_hinted else avg_conf
            
            # Check for a dimension match within the joined text
            dim_candidate = get_dimension_match(full_rotation_text)
            text = dim_candidate if dim_candidate else full_rotation_text
            is_dim = is_dimension(text)
            
            # Selection Logic:
            if is_dim:
                if not is_best_dim or effective_conf > best_conf:
                    best_text = text
                    best_conf = effective_conf
                    is_best_dim = True
            elif not is_best_dim:
                if effective_conf > best_conf and avg_conf > 0.4:
                    best_text = text
                    best_conf = effective_conf
        
        if best_text:
            logger.info(f"[PaddleOCR] Selected (hint={orientation_hint}, is_dim={is_best_dim}): '{best_text}'")
        return best_text, best_conf
        
    except Exception as e:
        logger.error(f"[PaddleOCR] Multi-rotation error: {e}")
        return "", 0.0
def run_paddle_ocr(cv_image) -> list:
    """
    Run PaddleOCR on a full page image and return formatted word-level data.
    
    Args:
        cv_image: Full page image (numpy array, BGR)
        
    Returns:
        list: A list of dicts with 'text', 'bbox' (x0, y0, x1, y1), and 'conf'.
    """
    if cv_image is None or cv_image.size == 0:
        return []
        
    try:
        ocr = get_paddle_ocr()
        # Perform OCR on the full image
        result = ocr.ocr(cv_image, cls=True)
        
        tokens = []
        if not result or not result[0]:
            return tokens
            
        for line in result[0]:
            # line[0] is the bounding box: [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]
            # line[1] is (text, confidence)
            bbox = line[0]
            text = line[1][0].strip()
            conf = float(line[1][1])
            
            if text:
                xs = [p[0] for p in bbox]
                ys = [p[1] for p in bbox]
                
                tokens.append({
                    'text': text,
                    'bbox': (min(xs), min(ys), max(xs), max(ys)),
                    'conf': conf
                })
                
        return tokens
        
    except Exception as e:
        logger.error(f"[PaddleOCR] Full page error: {e}")
        return []
