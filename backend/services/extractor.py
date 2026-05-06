import os
import cv2
import numpy as np
from pdf2image import convert_from_path
import logging
from .paddle_engine import run_multi_pass_ocr
from .tolerance_parser import parse_tolerance

logger = logging.getLogger(__name__)

# extractor.py
# Updated implementation using local PaddleOCR + Regex parsing.
# docTR is used for detection, PaddleOCR for extraction.

def extract_dimensions_from_bboxes(pdf_path: str, rectangles: list, viewer_context: dict = None, **kwargs) -> list:
    """
    Unified entry point for extracting dimensions from a list of bounding boxes.
    Step 12: Manual boxes use multi-pass PaddleOCR for precise extraction.
    """
    if not rectangles:
        return []

    try:
        # Step 1: Convert PDF to Image at 300 DPI
        pages = convert_from_path(pdf_path, dpi=300)
        if not pages:
            return []
        
        pil_image = pages[0]
        cv_image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
        img_h, img_w = cv_image.shape[:2]
        
        # Scaling factor: frontend is at 200 DPI, we are at 300 DPI
        scale = 300.0 / 200.0
        
        results = []
        
        for rect in rectangles:
            rect_id = rect.get('id')
            serial = rect.get('serial')
            
            # Geometry from frontend (assuming 200 DPI)
            # Apply scaling to 300 DPI
            x = int(float(rect.get('x', 0)) * scale)
            y = int(float(rect.get('y', 0)) * scale)
            w = int(float(rect.get('width', 0)) * scale)
            h = int(float(rect.get('height', 0)) * scale)
            
            # Step 7: Expand crop region slightly for better OCR context
            padding_w = int(w * 0.1)
            padding_h = int(h * 0.1)
            
            x_padded = max(0, x - padding_w)
            y_padded = max(0, y - padding_h)
            w_padded = min(img_w - x_padded, w + 2 * padding_w)
            h_padded = min(img_h - y_padded, h + 2 * padding_h)
            
            # 1. Crop region
            crop = cv_image[y_padded : y_padded + h_padded, x_padded : x_padded + w_padded]
            
            if crop.size == 0:
                continue

            # 2. OCR with Multi-Pass (Step 7 & 8)
            # This now handles contrast and rotation internally
            raw_text, conf = run_multi_pass_ocr(crop)
            
            # 3. Parse with upgraded tolerance_parser (Step 9)
            parsed = parse_tolerance(raw_text)
            
            results.append({
                'id': rect_id,
                'serial': serial,
                'dim': parsed.get('dim', '0'),
                'utol': parsed.get('utol', '0'),
                'ltol': parsed.get('ltol', '0'),
                'confidence': float(conf),
                'original': raw_text,
                'method': 'paddle_ocr_multi_pass',
                'is_manual': rect.get('method') == 'manual' or rect.get('is_manual', False)
            })

        # Sort by serial number
        results.sort(key=lambda r: (r.get('serial') is None, r.get('serial') or 999))
        return results

    except Exception as e:
        logger.exception("[Extractor] Error in extraction: %s", e)
        return []
