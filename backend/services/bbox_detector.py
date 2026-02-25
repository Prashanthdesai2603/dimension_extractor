from .doctr_engine import run_doctr_ocr
from .vector_engine import has_vector_text, extract_vector_text
from .grouping_engine import group_tokens
from .dimension_parser import extract_and_parse_dimensions
from pdf2image import convert_from_path

def detect_bounding_boxes(pdf_path: str) -> list:
    """
    Redesigned hybrid detection system:
    1. Check for vector text layer (PyMuPDF)
    2. Fallback to docTR OCR if no text layer exists
    3. Group and Classify ALL dimensions automatically
    """
    try:
        pages = convert_from_path(pdf_path, dpi=200)
        if not pages:
            return []
        
        pil_image = pages[0]
        img_width, img_height = pil_image.size
        
        # --- HYBRID DETECTION STEP ---
        if has_vector_text(pdf_path):
            print("[BBox Detector] Vector text layer detected. Using PyMuPDF.")
            tokens = extract_vector_text(pdf_path, dpi=200)
            method = "vector"
        else:
            print("[BBox Detector] No vector text found. Running docTR OCR fallback.")
            tokens = run_doctr_ocr(pdf_path, img_width, img_height)
            method = "ocr"
            
        if not tokens:
            return []
            
        # 1. Group tokens based on spatial proximity
        candidates = group_tokens(tokens)
        
        # 2. Parse and classify dimensions (All types)
        structured_dims = extract_and_parse_dimensions(candidates, img_width, img_height)
        
        print(f"[BBox Detector] Total dimensions classified: {len(structured_dims)} using {method}")
        
        # 3. Format for frontend
        results = []
        for d in structured_dims:
            x0, y0, x1, y1 = d['bbox']
            results.append({
                'id': f"box_{len(results)}",
                'x': float(x0),
                'y': float(y0),
                'width': float(x1 - x0),
                'height': float(y1 - y0),
                'text': d['original'],
                'dim': d['dim'],
                'utol': d['utol'],
                'ltol': d['ltol'],
                'method': method
            })
            
        return results

    except Exception as e:
        print(f"[BBox Detector] Error: {e}")
        return []
