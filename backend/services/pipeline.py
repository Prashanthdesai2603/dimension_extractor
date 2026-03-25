import logging
import os

import cv2
import numpy as np

from .paddle_engine import run_paddle_ocr
from .grouping_engine import group_tokens
from .dimension_validator import validate_dimension_candidates
from .vector_engine import extract_vector_text, has_vector_text
from pdf2image import convert_from_path

logger = logging.getLogger(__name__)

def pdf_to_image(pdf_path: str, page_number: int = 0, dpi: int = 200) -> np.ndarray:
    """
    Convert a specific page of a PDF to a numpy array (OpenCV image).
    """
    pages = convert_from_path(pdf_path, dpi=dpi)
    if not pages:
        raise ValueError(f"Could not convert PDF: {pdf_path}")
    page_number = min(page_number, len(pages) - 1)
    pil_image = pages[page_number]
    cv_image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
    return cv_image

def process_drawing(pdf_path: str, output_image_path: str) -> dict:
    """
    Hybrid extraction pipeline: Vector extraction with OCR fallback.
    """
    try:
        # Step 1: Detect PDF type and extract tokens
        is_vector = has_vector_text(pdf_path)
        
        # We still need the image for annotation and fallback
        # Always convert to image first to get page dimensions
        cv_image = pdf_to_image(pdf_path, page_number=0, dpi=200)
        img_height, img_width = cv_image.shape[:2]
        
        tokens = []
        method = "OCR"

        if is_vector:
            logger.info("[Pipeline] Vector text detected in %s", pdf_path)
            # extract_vector_text() already returns bboxes scaled to dpi=200
            # pixel space — do NOT multiply by scale again (that was a bug).
            raw_vector_tokens = extract_vector_text(pdf_path, dpi=200)
            for vt in raw_vector_tokens:
                tokens.append({
                    'text':   vt['text'],
                    'bbox':   vt['bbox'],   # already in 200-DPI pixels
                    'method': 'vector',
                })
            method = "Vector"
        
        # Fallback to OCR if vector extraction returned nothing or it is a scan
        if not tokens:
            logger.info("[Pipeline] Falling back to PaddleOCR for %s", pdf_path)
            tokens = run_paddle_ocr(cv_image)
            method = "PaddleOCR"

        # Step 2: Grouping
        candidates = group_tokens(tokens)
        
        # Step 3: Validation and Filtering
        valid_dimensions, noise_count = validate_dimension_candidates(candidates, img_width, img_height)
        
        # Step 4: Annotation (only valid dimensions)
        annotated_image = draw_annotations(cv_image, valid_dimensions)
        
        # Step 5: Save
        os.makedirs(os.path.dirname(output_image_path), exist_ok=True)
        cv2.imwrite(output_image_path, annotated_image)
        
        # Results
        dimension_texts = [d['text'] for d in valid_dimensions]
        
        return {
            'success': True,
            'dimensions': dimension_texts,
            'total_detected': len(candidates),
            'valid_dimensions': len(valid_dimensions),
            'filtered_noise': noise_count,
            'method': method,
            'error': None
        }

    except Exception as exc:
        logger.exception("[Pipeline] Unhandled error: %s", exc)
        return {
            'success':        False,
            'dimensions':     [],
            'total_detected': 0,
            'valid_dimensions': 0,
            'filtered_noise': 0,
            'error':          str(exc)
        }

def draw_annotations(cv_image: np.ndarray, dimensions: list) -> np.ndarray:
    """
    Draws bounding boxes and labels for validated dimensions.
    """
    annotated = cv_image.copy()
    BOX_COLOR = (0, 0, 255) # Red
    TEXT_COLOR = (0, 0, 150) # Dark red
    
    for dim in dimensions:
        bbox = dim['bbox']
        x1, y1, x2, y2 = map(int, bbox)
        
        # Draw rectangle
        cv2.rectangle(annotated, (x1, y1), (x2, y2), BOX_COLOR, 2)
        
        # Draw label
        label = dim['text']
        cv2.putText(
            annotated, 
            label, 
            (x1, max(y1 - 5, 20)), 
            cv2.FONT_HERSHEY_SIMPLEX, 
            0.6, 
            TEXT_COLOR, 
            1, 
            cv2.LINE_AA
        )
        
    return annotated
