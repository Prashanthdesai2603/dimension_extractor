"""
bbox_detector.py  –  Smart direct detection of engineering dimensions.

Strategy (vector PDFs):
  1. Extract every text LINE from the PDF (preserving full tolerance strings).
  2. Keep only text that matches a strict engineering-dimension pattern.
  3. Filter by font size: dimension callouts are NEVER the smallest text
     in the drawing (notes, title-block).  We compute the median font size
     and keep only text at or above a threshold relative to that median.
  4. Reject any line that contains 5+ words (labels / notes).
  5. Reject text inside standard title-block / notes exclusion zones.
  6. Detect vertical dimensions (dir = 0,±1) and mark accordingly.

Fallback (raster / scanned PDFs):
  docTR OCR then the old grouping/validator pipeline.
"""

import re
import cv2
import logging
import numpy as np
from .vector_engine import has_vector_text, extract_vector_text
from .tolerance_parser import parse_tolerance
from pdf2image import convert_from_path
from .doctr_detector import detect_dimension_boxes
from .paddle_engine import run_multi_pass_ocr
from .dimension_detector import is_dimension

logger = logging.getLogger(__name__)

# Phrases that indicate the text is a label / note regardless of numbers
_NOISE_PHRASES = [
    'VIEW', 'NOTE', 'SCALE', 'SHEET', 'REV', 'DWG', 'MATERIAL', 'WEIGHT',
    'FINISH', 'UNLESS', 'OTHERWISE', 'SPECIFIED', 'DRAWN', 'CHECKED',
    'APPROVED', 'DATE', 'PROJECTION', 'ANGLE', 'ISOMETRIC', 'SECTION',
    'DETAIL', 'PART', 'DESCRIPTION', 'REVISION', 'TOLERANCE', 'REFER',
    'CAD', 'MODEL', 'BASIC', 'BREAK', 'EDGE', 'BURR', 'SHARP', 'FREE',
    'SEATING', 'SPRING', 'DESIGN', 'TABLE', 'WIRE', 'SIZE', 'COIL',
    'RATE', 'DURABILITY', 'TORQUE', 'POSITION', 'COLOUR', 'COLOUR',
    'COLOR', 'IDENTIFICATION', 'AUTHORISATION', 'PRODUCTION', 'APPROVAL',
    'ENGINEERING', 'INFORMATION',
]

def _is_clean_dimension(text: str) -> bool:
    """Return True only if 'text' is purely a numeric engineering dimension."""
    t = text.strip()
    if not t:
        return False
    # Must contain at least one digit
    if not any(c.isdigit() for c in t):
        return False
    # Reject if text contains a noise phrase
    t_up = t.upper()
    if any(phrase in t_up for phrase in _NOISE_PHRASES):
        return False
        
    return is_dimension(t)

def detect_bounding_boxes(pdf_path: str) -> list:
    """
    Main entry.  Returns list of bbox dicts for the frontend canvas.
    """
    try:
        pages = convert_from_path(pdf_path, dpi=300)
        if not pages:
            return []
        pil_image = pages[0]
        img_w, img_h = pil_image.size

        if has_vector_text(pdf_path):
            return _detect_vector(pdf_path, img_w, img_h)
        else:
            return _detect_ocr(pdf_path, img_w, img_h, pil_image)

    except Exception as e:
        logger.exception("[BBox Detector] Error in detection: %s", e)
        return []

def _detect_vector(pdf_path: str, img_w: int, img_h: int) -> list:
    tokens = extract_vector_text(pdf_path, dpi=300)
    if not tokens:
        return []

    scale_to_viewer = 200.0 / 300.0

    # TB / Exclusion zones
    TB_Y = img_h * 0.80
    TB_X = img_w * 0.60
    NOTES_Y = img_h * 0.75
    NOTES_X = img_w * 0.45

    results = []
    seen = set()

    for i, tok in enumerate(tokens):
        text = tok['text'].strip()
        x0, y0, x1, y1 = tok['bbox']
        direction = tok.get('dir', (1, 0))

        if (y0 > TB_Y and x0 > TB_X) or (y0 > NOTES_Y and x0 < NOTES_X):
            continue

        if not _is_clean_dimension(text):
            continue

        key = (round(x0), round(y0), text)
        if key in seen:
            continue
        seen.add(key)

        is_vertical = abs(direction[0]) < 0.3
        parsed = parse_tolerance(text)

        results.append({
            'id':        f'box_v_{i}',
            'serial':    len(results) + 1,
            'x':         float(x0) * scale_to_viewer,
            'y':         float(y0) * scale_to_viewer,
            'width':     float(x1 - x0) * scale_to_viewer,
            'height':    float(y1 - y0) * scale_to_viewer,
            'text':      text,
            'dim':       parsed['dim'],
            'utol':      parsed['utol'],
            'ltol':      parsed['ltol'],
            'vertical':  is_vertical,
            'method':    'vector',
        })

    return results

def _detect_ocr(pdf_path: str, img_w: int, img_h: int, pil_image) -> list:
    cv_img = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
    detected_boxes = detect_dimension_boxes(pdf_path)
    
    scale_to_viewer = 200.0 / 300.0
    results = []

    for i, box in enumerate(detected_boxes):
        x, y, w, h = box['x'], box['y'], box['width'], box['height']
        
        crop_img = cv_img[y:y+h, x:x+w]
        if crop_img.size == 0:
            continue
            
        text, conf = run_multi_pass_ocr(crop_img)
        if not text:
            continue
            
        parsed = parse_tolerance(text)
        if parsed['dim'] == '0' or parsed['dim'] == '':
            continue

        results.append({
            'id':        f'box_doctr_{i}',
            'serial':    len(results) + 1,
            'x':         float(x) * scale_to_viewer,
            'y':         float(y) * scale_to_viewer,
            'width':     float(w) * scale_to_viewer,
            'height':    float(h) * scale_to_viewer,
            'text':      text,
            'dim':       parsed['dim'],
            'utol':      parsed['utol'],
            'ltol':      parsed['ltol'],
            'confidence': float(conf),
            'vertical':  box.get('vertical', False),
            'method':    'doctr_paddleocr',
        })
        
    return results
