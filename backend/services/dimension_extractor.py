import logging
import fitz
import cv2
import numpy as np
from .dimension_detector import get_dimension_match, is_dimension
from .tolerance_parser import parse_tolerance
from .vector_engine import find_text_in_region
from .paddle_engine import extract_text_from_region

logger = logging.getLogger(__name__)

# dimension_extractor.py
# Refactored to remove PaddleOCR and use Google Vision.

def detect_vector_text(pdf_path: str, page_number: int = 0, min_chars: int = 10) -> bool:
    try:
        doc = fitz.open(pdf_path)
        if len(doc) == 0 or page_number >= len(doc): return False
        page = doc[page_number]
        text = page.get_text().strip()
        return len(text) >= min_chars
    except:
        return False

def extract_from_vector(pdf_path: str, page_number: int = 0, dpi: int = 200, only_dimensions: bool = True):
    tokens = []
    try:
        doc = fitz.open(pdf_path)
        page = doc[page_number]
        scale = dpi / 72.0
        words = page.get_text("words") # (x0, y0, x1, y1, "word", block_no, line_no, word_no)
        for w in words:
            text = w[4]
            if only_dimensions and not is_dimension(text): continue
            tokens.append({
                "text": text,
                "bbox": [w[0]*scale, w[1]*scale, w[2]*scale, w[3]*scale]
            })
        doc.close()
    except Exception as e:
        logger.error(f"Vector extraction error: {e}")
    return tokens

def extract_with_ocr(pdf_path, bbox_200dpi, page_number=0, **kwargs):
    """
    OCR fallback using Google Vision.
    """
    x, y, w, h = bbox_200dpi
    try:
        doc = fitz.open(pdf_path)
        page = doc[page_number]
        scale = 72.0 / 200.0
        rect = fitz.Rect(x*scale, y*scale, (x+w)*scale, (y+h)*scale)
        # Pad slightly
        rect.x0 -= 5; rect.y0 -= 5; rect.x1 += 5; rect.y1 += 5
        
        pix = page.get_pixmap(clip=rect, dpi=300)
        img_np = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
        img_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR) if pix.n == 3 else cv2.cvtColor(img_np, cv2.COLOR_RGBA2BGR)
        
        _, encoded = cv2.imencode('.jpg', img_bgr)
        text = extract_text_from_region(img_bgr)
        return text, 0.9 if text else 0.0
    except Exception as e:
        logger.error(f"OCR error in dimension_extractor: {e}")
        return "", 0.0

def extract_dimension_value(pdf_path, bbox_200dpi, **kwargs):
    # Simplified hybrid extraction
    text, conf = extract_with_ocr(pdf_path, bbox_200dpi, **kwargs)
    if text:
        parsed = parse_tolerance(text)
        return {
            "text": text, "method": "ocr", "conf": conf,
            "dim": parsed["dim"], "utol": parsed["utol"], "ltol": parsed["ltol"]
        }
    return {"text": "", "method": "none", "conf": 0, "dim": "", "utol": "0", "ltol": "0"}
