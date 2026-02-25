import os
import cv2
import numpy as np
from pdf2image import convert_from_path
from .model_loader import get_ocr_model
from .tolerance_parser import parse_tolerance

def extract_dimensions_from_bboxes(pdf_path: str, rectangles: list) -> list:
    """
    For each rectangle:
    1. Crop region from image
    2. Run docTR
    3. Parse dimension and tolerance
    4. Return structured output
    """
    if not rectangles:
        return []

    try:
        # Convert PDF to Image (DPI 200 to match frontend coordinates)
        pages = convert_from_path(pdf_path, dpi=200)
        if not pages:
            return []
        
        # We only work with the first page for now
        pil_image = pages[0]
        cv_image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
        img_h, img_w = cv_image.shape[:2]
        
        ocr_model = get_ocr_model()
        results = []
        
        for rect in rectangles:
            # Preserve original ID for frontend mapping
            rect_id = rect.get('id')
            
            # Coordinates from frontend
            x = int(rect.get('x', 0))
            y = int(rect.get('y', 0))
            w = int(rect.get('width', 0))
            h = int(rect.get('height', 0))
            
            # Boundary checks
            x = max(0, min(x, img_w - 1))
            y = max(0, min(y, img_h - 1))
            w = max(1, min(w, img_w - x))
            h = max(1, min(h, img_h - y))
            
            # 1. Crop region
            crop = cv_image[y : y + h, x : x + w]
            
            # 2. Run docTR on crop
            crop_rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
            ocr_result = ocr_model([crop_rgb])
            
            # Extract text
            extracted_words = []
            for page in ocr_result.pages:
                for block in page.blocks:
                    for line in block.lines:
                        for word in line.words:
                            extracted_words.append(word.value)
            
            # Grouping tokens manually if needed, or join
            raw_text = " ".join(extracted_words) 
            raw_text = raw_text.replace('± ', '±').replace(' +', '+').replace(' -', '-')
            
            print(f"Detected text: {raw_text}")
            
            # 3. Parse dimension and tolerance
            parsed = parse_tolerance(raw_text)
            
            results.append({
                'id': rect_id,
                'dim': parsed['dim'],
                'utol': parsed['utol'],
                'ltol': parsed['ltol'],
                'original': raw_text
            })

        return results

    except Exception as e:
        print(f"[Extractor Service] Error: {e}")
        return []
