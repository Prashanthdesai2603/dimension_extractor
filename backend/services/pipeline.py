import logging
import os
import cv2
import numpy as np
from pdf2image import convert_from_path
from .doctr_detector import detect_dimension_boxes
from .paddle_engine import run_multi_pass_ocr
from .tolerance_parser import parse_tolerance, normalize_ocr_text, format_structured_dimension
from .symbol_detector import run_advanced_ocr_pipeline

logger = logging.getLogger(__name__)

def pdf_to_image(pdf_path: str, page_number: int = 0, dpi: int = 300) -> np.ndarray:
    pages = convert_from_path(pdf_path, dpi=dpi)
    if not pages:
        raise ValueError(f"Could not convert PDF: {pdf_path}")
    page_number = min(page_number, len(pages) - 1)
    pil_image = pages[page_number]
    cv_image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
    return cv_image

def process_drawing(pdf_path: str, output_image_path: str) -> dict:
    """
    Main pipeline:
    1. PDF -> Image
    2. docTR -> Detect dimension regions
    3. PaddleOCR -> Extract text from regions
    4. Tolerance Parser -> Format output
    """
    try:
        cv_image = pdf_to_image(pdf_path, page_number=0, dpi=300)
        
        print("\n" + "="*50)
        print(">>> [PROCESS] docTR is detecting dimension regions...")
        print("="*50)
        
        # Step 2: Detect dimension regions using docTR
        detected_boxes = detect_dimension_boxes(pdf_path)
        
        valid_dimensions = []
        
        print(f">>> [PROCESS] Extracting text from {len(detected_boxes)} detected regions...")
        
        for box in detected_boxes:
            x, y, w, h = box['x'], box['y'], box['width'], box['height']
            
            # Crop region
            crop_img = cv_image[y:y+h, x:x+w]
            if crop_img.size == 0:
                continue
                
            # Step 7, 8, 9: Run advanced OCR with Symbol Helper Models
            text, conf = run_advanced_ocr_pipeline(crop_img)
            
            if not text:
                continue
                
            # Step 9: Parse tolerance
            parsed = parse_tolerance(text)
            
            # Filter out obvious non-dimensions if they slipped through
            if parsed['dim'] == '0' or parsed['dim'] == '':
                continue
                
            valid_dimensions.append({
                'text': text,
                'bbox': [x, y, x + w, y + h],
                'parsed': parsed,
                'confidence': conf
            })

        print(f">>> [PIPELINE] Successfully processed {len(valid_dimensions)} dimensions.")

        # Draw annotations for visual feedback
        annotated_image = draw_annotations(cv_image, valid_dimensions)
        
        os.makedirs(os.path.dirname(output_image_path), exist_ok=True)
        cv2.imwrite(output_image_path, annotated_image)
        
        output_dims = [format_structured_dimension(d['parsed']) for d in valid_dimensions]

        return {
            'success': True,
            'dimensions': output_dims,
            'valid_dimensions': len(valid_dimensions),
            'method': "docTR + PaddleOCR + SymbolHelper",
            'error': None
        }

    except Exception as exc:
        logger.exception("[Pipeline] Unhandled error: %s", exc)
        return {'success': False, 'error': str(exc)}

def draw_annotations(cv_image: np.ndarray, dimensions: list) -> np.ndarray:
    annotated = cv_image.copy()
    for d in dimensions:
        x1, y1, x2, y2 = map(int, d['bbox'])
        # Draw rectangle
        # Step 11: color low-confidence boxes differently
        color = (0, 0, 255) # Red for high confidence
        if d['confidence'] < 0.6:
            color = (0, 165, 255) # Orange for low confidence
            
        cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
        
        p = d['parsed']
        label = f"{p['dim']} (+{p['utol']}/{p['ltol']})"
        cv2.putText(annotated, label, (x1, max(y1 - 5, 20)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 1)
    return annotated
