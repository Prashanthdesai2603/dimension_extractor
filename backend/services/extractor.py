"""
extractor.py
Extracts dimensions from user-drawn bounding boxes.

Priority order for each box:
  1. FAST PATH  – box already has text/dim from the auto-detector (vector).
                  Parse directly.
  2. VECTOR LOOKUP – box has no stored text (manually drawn) AND the PDF has
                    a vector text layer.  Use PyMuPDF spatial search to find
                    which text spans fall inside the drawn region.  This is
                    100% accurate for CAD vector PDFs.
  3. OCR FALLBACK – PDF has no vector text (scanned/raster) or vector lookup
                   found nothing inside the box.  Crop the image, run docTR
                   with 3-orientation trial.
  4. PLACEHOLDER   – manual box where everything failed.  Return an empty row
                   so the user can type the value themselves.
"""
import re
import os
import cv2
import numpy as np
import fitz  # PyMuPDF
from pdf2image import convert_from_path
from .model_loader import get_ocr_model
from .tolerance_parser import parse_tolerance
from .vector_engine import has_vector_text, extract_all_spans, find_text_in_region
from .dimension_detector import is_dimension, get_dimension_match


# ---------------------------------------------------------------------------
# OCR helpers (fallback only)
# ---------------------------------------------------------------------------

def _is_curved(text: str) -> bool:
    """Heuristic to detect if text might be curved — often has weird symbols or spaces."""
    if not text: return False
    # If text is extremely sparse or has multiple symbols without digits nearby
    # This is a weak heuristic, we'll mostly rely on the manual box flag.
    return " " in text and len(text) > 4

def _preprocess(img, is_curved=False, is_low_res=False):
    """
    Enhanced preprocessing including upscaling and Gaussian blur for curved text.
    """
    h, w = img.shape[:2]
    
    # Selection logic for upscale
    factor = 3.0 if is_low_res else 2.0
    img = cv2.resize(img, (0, 0), fx=factor, fy=factor, interpolation=cv2.INTER_CUBIC)
    
    # Adaptive thresholding/blur for curved text
    if is_curved:
        img = cv2.GaussianBlur(img, (3, 3), 0)
        # We avoid hard thresholding as docTR prefers RGB/Grayscale gradients
    
    # Standard grayscale/CLAHE
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    gray = clahe.apply(gray)
    
    return cv2.cvtColor(gray, cv2.COLOR_GRAY2RGB)


def _ocr_one(model, crop_rgb) -> tuple:
    """
    Run docTR and merge words. 
    Returns (merged_text, confidence_score).
    """
    try:
        res = model([crop_rgb])
        words_data = []
        confidences = []
        
        for pg in res.pages:
            for bl in pg.blocks:
                for ln in bl.lines:
                    for w in ln.words:
                        words_data.append({
                            'text': w.value,
                            'ymin': w.geometry[0][1],
                            'ymax': w.geometry[1][1],
                            'xmin': w.geometry[0][0],
                            'xmax': w.geometry[1][0],
                            'conf': w.confidence
                        })
                        confidences.append(w.confidence)
        
        if not words_data:
            return "", 0.0

        # Sort and group by lines
        words_data.sort(key=lambda x: ((x['ymin'] + x['ymax']) / 2, (x['xmin'] + x['xmax']) / 2))
        
        lines = []
        if words_data:
            current_line = [words_data[0]]
            for i in range(1, len(words_data)):
                prev = current_line[-1]
                curr = words_data[i]
                prev_yc = (prev['ymin'] + prev['ymax']) / 2
                curr_yc = (curr['ymin'] + curr['ymax']) / 2
                h = max(prev['ymax'] - prev['ymin'], 0.001)
                
                if abs(curr_yc - prev_yc) < (h * 0.4):
                    current_line.append(curr)
                else:
                    lines.append(current_line)
                    current_line = [curr]
            lines.append(current_line)

        final_lines = []
        for line in lines:
            line.sort(key=lambda x: x['xmin'])
            line_str = ""
            for i, w in enumerate(line):
                if i == 0:
                    line_str = w['text']
                else:
                    gap = w['xmin'] - line[i-1]['xmax']
                    line_str += ("" if gap < 0.01 else " ") + w['text']
            final_lines.append(line_str)
            
        full_text = " ".join(final_lines).strip()
        avg_conf = np.mean(confidences) if confidences else 0.0
        return full_text, avg_conf
        
    except Exception as e:
        print(f"[OCR] Error: {e}")
        return "", 0.0


def _best_ocr(model, crop_rgb):
    """
    Try 4 orientations (0, 90, 180, 270) and return the best valid result.
    Priority: Highest confidence AND valid numeric pattern.
    """
    orientations = [
        (crop_rgb, 0),
        (cv2.rotate(crop_rgb, cv2.ROTATE_90_CLOCKWISE), 90),
        (cv2.rotate(crop_rgb, cv2.ROTATE_180), 180),
        (cv2.rotate(crop_rgb, cv2.ROTATE_90_COUNTERCLOCKWISE), 270),
    ]
    
    results = []
    for img, angle in orientations:
        text, conf = _ocr_one(model, img)
        # Check if text matches dimension pattern
        valid_dim = is_dimension(text)
        results.append({
            'text': text,
            'conf': conf,
            'valid': valid_dim
        })
    
    # 1. Look for valid results first
    valid_results = [r for r in results if r['valid'] and r['conf'] > 0.3]
    if valid_results:
        # Pick the one with highest confidence
        best = max(valid_results, key=lambda x: x['conf'])
        return best['text'], best['conf']
    
    # 2. Fallback to highest confidence if at least something was found
    if results:
        best_overall = max(results, key=lambda x: x['conf'])
        if best_overall['conf'] > 0.4: # Higher threshold for non-validated strings
             return best_overall['text'], best_overall['conf']

    return "", 0.0


# ---------------------------------------------------------------------------
# Result builders
# ---------------------------------------------------------------------------

def _make_result(rid, serial: int, text: str, is_manual: bool) -> dict:
    """Parse text into dim/utol/ltol and build result dict."""
    parsed = parse_tolerance(text)
    return {
        'id':        rid,
        'serial':    serial,
        'dim':       parsed['dim'],
        'utol':      parsed['utol'],
        'ltol':      parsed['ltol'],
        'original':  text,
        'is_manual': is_manual,
    }


def _make_result_manual(rid, serial: int, text: str) -> dict:
    """
    Special result builder for manual boxes: 
    Prioritizes the structured result if any valid pieces are extracted.
    Also strips the serial number if it's trapped in the text.
    """
    text = str(text or '').strip()
    
    # 1. Strip known serial index from text to avoid picking it as dimension
    # Common formats: "1 25.4", "(1) 25.4", "1: 25.4", "1. 25.4"
    if serial:
        s_str = str(serial)
        # Patterns to remove serial balloon text (at start or end)
        patterns = [
            rf'^{s_str}\s+',          # "1 ..."
            rf'^\({s_str}\)\s*',      # "(1) ..."
            rf'^\[{s_str}\]\s*',      # "[1] ..."
            rf'^{s_str}[:.-]\s*',     # "1: ..." or "1. ..."
            rf'\b{s_str}$',           # "... 1"
        ]
        temp_text = text
        for p in patterns:
            temp_text = re.sub(p, '', temp_text, flags=re.IGNORECASE).strip()
        
        # If we removed the serial and still have digits left, use the cleaned text
        if any(c.isdigit() for c in temp_text):
            text = temp_text

    # Try parsing for structure
    parsed = parse_tolerance(text)
    
    # If a dimension was successfully extracted, use the structured result
    if parsed['dim'] and any(c.isdigit() for c in str(parsed['dim'])):
        return {
            'id':        rid,
            'serial':    serial,
            'dim':       str(parsed['dim']),
            'utol':      str(parsed['utol']),
            'ltol':      str(parsed['ltol']),
            'original':  text,
            'is_manual': True,
        }

    # Absolute fallback — just the raw text
    return {
        'id':        rid,
        'serial':    serial,
        'dim':       text,
        'utol':      '0',
        'ltol':      '0',
        'original':  text,
        'is_manual': True,
    }


def _make_placeholder(rid, serial: int) -> dict:
    """Empty row for a manual box where all extraction failed."""
    return {
        'id':        rid,
        'serial':    serial,
        'dim':       '',
        'utol':      '0',
        'ltol':      '0',
        'original':  '',
        'is_manual': True,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_dimensions_from_bboxes(pdf_path: str, rectangles: list) -> list:
    """
    Extract dimension values from all bounding boxes.

    rectangles: list of { id, x, y, width, height, text?, dim?, utol?, ltol?, method? }
                Coordinates are in 200 DPI image pixel space.
    """
    if not rectangles:
        return []

    # -----------------------------------------------------------------------
    # Split: already-known text (auto-detected) vs needs-lookup (manual)
    # -----------------------------------------------------------------------
    fast_results   = []
    lookup_queue   = []   # (rect, is_manual)

    for rect in rectangles:
        known_text = str(rect.get('text', '') or '').strip()
        known_dim  = str(rect.get('dim',  '') or '').strip()
        serial     = rect.get('serial')
        is_manual  = (rect.get('method') == 'manual') or (known_text in ('', 'Manual'))

        if not is_manual and known_text and any(c.isdigit() for c in known_text):
            # ---- FAST PATH ----
            parsed = parse_tolerance(known_text)
            if known_dim and known_dim not in ('', '0', 'null', 'undefined', 'None'):
                parsed['dim'] = known_dim
            utol = str(rect.get('utol', '0') or '0').strip()
            ltol = str(rect.get('ltol', '0') or '0').strip()
            if utol not in ('', '0', 'null', 'undefined', 'None'):
                parsed['utol'] = utol
            if ltol not in ('', '0', 'null', 'undefined', 'None'):
                parsed['ltol'] = ltol
            fast_results.append({
                'id':        rect.get('id'),
                'serial':    serial,
                'dim':       parsed['dim'],
                'utol':      parsed['utol'],
                'ltol':      parsed['ltol'],
                'original':  known_text,
                'is_manual': False,
            })
        else:
            lookup_queue.append((rect, is_manual))

    print(f"[Extractor] Fast={len(fast_results)}, Lookup-queue={len(lookup_queue)}")

    if not lookup_queue:
        return fast_results

    # -----------------------------------------------------------------------
    # VECTOR LOOKUP — load spans once using PyMuPDF
    # -----------------------------------------------------------------------
    vector_spans = []
    if has_vector_text(pdf_path):
        try:
            vector_spans = extract_all_spans(pdf_path, dpi=200)
            print(f"[Extractor] Vector spans loaded: {len(vector_spans)}")
        except Exception as e:
            print(f"[Extractor] Vector span load error: {e}")

    # -----------------------------------------------------------------------
    # Process each lookup box
    # -----------------------------------------------------------------------
    results = []
    ocr_model = None
    doc = None

    try:
        doc = fitz.open(pdf_path)
        page = doc[0] if len(doc) > 0 else None

        for rect, is_manual in lookup_queue:
            rid = rect.get('id')
            serial = rect.get('serial')
            try:
                x_200 = float(rect.get('x', 0))
                y_200 = float(rect.get('y', 0))
                w_200 = float(rect.get('width',  50))
                h_200 = float(rect.get('height', 20))
                rot   = float(rect.get('rotation', 0) or 0)

                # If rotated, compute AABB for better spatial lookup and cropping
                if abs(rot) > 0.1:
                    rad = np.radians(rot)
                    cos_a, sin_a = np.cos(rad), np.sin(rad)
                    # Corners relative to (x, y)
                    corners = [(0,0), (w_200, 0), (w_200, h_200), (0, h_200)]
                    new_pts = []
                    for cx, cy in corners:
                        nx = x_200 + (cx * cos_a - cy * sin_a)
                        ny = y_200 + (cx * sin_a + cy * cos_a)
                        new_pts.append((nx, ny))
                    xs = [p[0] for p in new_pts]
                    ys = [p[1] for p in new_pts]
                    
                    # Update active region to AABB
                    old_x, old_y = x_200, y_200
                    x_200, y_200 = min(xs), min(ys)
                    w_200, h_200 = max(xs) - x_200, max(ys) - y_200
                    print(f"[Extractor] Rotated box {rid} (rot={rot:.1f}°) -> AABB x={x_200:.1f}, y={y_200:.1f}, w={w_200:.1f}, h={h_200:.1f}")
            except Exception:
                if is_manual:
                    results.append(_make_placeholder(rid, serial))
                continue

            # ----- Step 1: Vector spatial lookup -----
            found_text = ""
            if vector_spans:
                # For manual boxes, use a tighter region to avoid "wrong nearby value"
                expand_val = 4 if is_manual else 8
                found_text = find_text_in_region(
                    vector_spans,
                    x_200 - expand_val, y_200 - expand_val,
                    w_200 + expand_val * 2, h_200 + expand_val * 2
                )
                if is_manual and found_text:
                    print(f"[Manual Vector] id={rid} found='{found_text}'")

            if found_text and any(c.isdigit() for c in found_text):
                if is_manual:
                    results.append(_make_result_manual(rid, serial, found_text))
                else:
                    results.append(_make_result(rid, serial, found_text, is_manual))
                continue

            # ----- Step 2: OCR fallback (Dynamic DPI & Smart Crop) -----
            try:
                # 1. Coordinate Conversion: Viewer (200 DPI) -> PDF (72 DPI)
                s = 72.0 / 200.0
                xp, yp = x_200 * s, y_200 * s
                wp, hp = w_200 * s, h_200 * s

                # 2. Dynamic DPI & Padding
                pad = 25 if is_manual else 15
                clip = fitz.Rect(xp - pad, yp - pad, xp + wp + pad, yp + hp + pad)
                
                is_low_res = wp < 40 
                dpi = 500 if is_low_res else 300
                
                if page:
                    pix = page.get_pixmap(clip=clip, dpi=dpi)
                    img_np = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
                    img_rgb = cv2.cvtColor(img_np, cv2.COLOR_BGR2RGB) if pix.n == 3 else cv2.cvtColor(img_np, cv2.COLOR_GRAY2RGB)

                    # 3. Preprocessing & Upscaling
                    img_final = _preprocess(img_rgb, is_curved=is_manual, is_low_res=is_low_res)
                    
                    if ocr_model is None:
                        ocr_model = get_ocr_model()

                    # 4. Rotation Loop & Selection
                    ocr_text, ocr_conf = _best_ocr(ocr_model, img_final)
                    
                    if ocr_text:
                        print(f"[OCR] id={rid} dpi={dpi} text='{ocr_text}' conf={ocr_conf:.2f}")

                    # 5. Validation Check
                    if ocr_text and ocr_conf > 0.4:
                        if is_manual:
                            results.append(_make_result_manual(rid, serial, ocr_text))
                        else:
                            results.append(_make_result(rid, serial, ocr_text, is_manual))
                        continue
            except Exception as e:
                print(f"[Extractor] OCR error for {rid}: {e}")

            # ----- Step 3: Final Placeholder -----
            if is_manual:
                results.append(_make_placeholder(rid, serial))

    finally:
        if doc: doc.close()

    final = fast_results + results
    # Sort by serial number to maintain consistent mapping with drawing
    final.sort(key=lambda x: x.get('serial') or 999)
    
    print(f"[Extractor] Completed. Total={len(final)}")
    return final
