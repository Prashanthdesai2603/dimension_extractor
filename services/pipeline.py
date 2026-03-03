import os
import cv2
import numpy as np
from .vector_engine import extract_vector_text, has_vector_text
from .doctr_engine import run_doctr_ocr
from .grouping_engine import group_tokens
from .dimension_validator import validate_dimension_candidates
from pdf2image import convert_from_path

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
            print(f"[Pipeline] Vector text detected in {pdf_path}")
            # Vector extract
            raw_vector_tokens = extract_vector_text(pdf_path)
            # Standardize vector tokens to match our internal format
            # PyMuPDF coords are in points, image is in pixels (DPI=200)
            # 1 point = 1/72 inch. At 200 DPI, 1 point = 200/72 pixels ≈ 2.77 pixels
            scale = 200 / 72.0
            
            for vt in raw_vector_tokens:
                tokens.append({
                    'text': vt['text'],
                    'bbox': (
                        vt['bbox'][0] * scale,
                        vt['bbox'][1] * scale,
                        vt['bbox'][2] * scale,
                        vt['bbox'][3] * scale
                    )
                })
            method = "Vector"
        
        # Fallback to OCR if vector extraction returned nothing or if it's a scan
        if not tokens:
            print(f"[Pipeline] Falling back to docTR OCR for {pdf_path}")
            tokens = run_doctr_ocr(pdf_path, img_width, img_height)
            method = "docTR"

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

    except Exception as e:
        print(f"[Pipeline] Error: {e}")
        import traceback
        traceback.print_exc()
        return {
            'success': False,
            'dimensions': [],
            'total_detected': 0,
            'valid_dimensions': 0,
            'filtered_noise': 0,
            'error': str(e)
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
