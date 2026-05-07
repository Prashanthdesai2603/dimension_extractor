import logging
import re
import cv2
import numpy as np
from .symbol_model_loader import get_symbol_models, preprocess_for_symbols

logger = logging.getLogger(__name__)

def detect_and_correct_symbols(crop_img, ocr_text):
    """
    Main service to improve OCR text using symbol detection models.
    Input: crop_img (CV2 image), ocr_text (string from PaddleOCR)
    Output: corrected_text
    """
    if crop_img is None or crop_img.size == 0:
        return ocr_text

    original_text = ocr_text
    models = get_symbol_models()
    if not models:
        return ocr_text

    # Preprocess image for detection pass
    processed_img = preprocess_for_symbols(crop_img)
    
    detected_symbols = []
    
    # 1. Run YOLO models for common symbols
    # Diameter and general symbols
    for m_key in ['diameter', 'phi', 'best']:
        if m_key in models:
            results = models[m_key](crop_img, verbose=False)
            for res in results:
                for box in res.boxes:
                    conf = float(box.conf[0])
                    cls_id = int(box.cls[0])
                    label = res.names[cls_id]
                    
                    # Map common classes to symbols
                    if 'diam' in label.lower() or 'phi' in label.lower() or label == '0':
                        detected_symbols.append({'sym': 'Ø', 'x': float(box.xywh[0][0]), 'conf': conf})
                    elif 'tol' in label.lower() or 'plus' in label.lower() or 'pm' in label.lower():
                        detected_symbols.append({'sym': '±', 'x': float(box.xywh[0][0]), 'conf': conf})
                    elif conf > 0.4:
                        # Fallback to label name if it's a known symbol
                        detected_symbols.append({'sym': label, 'x': float(box.xywh[0][0]), 'conf': conf})

    # Tolerance symbols (±)
    for m_key in ['trt', 'trt1', 'trt2']:
        if m_key in models:
            results = models[m_key](crop_img, verbose=False)
            for res in results:
                for box in res.boxes:
                    conf = float(box.conf[0])
                    if conf > 0.4:
                        detected_symbols.append({'sym': '±', 'x': float(box.xywh[0][0]), 'conf': conf})

    # Text recovery (for missing digits)
    if 'text' in models:
        results = models['text'](crop_img, verbose=False)
        for res in results:
            for box in res.boxes:
                conf = float(box.conf[0])
                cls_id = int(box.cls[0])
                # Assuming class IDs correspond to digits or symbols
                # This is a simplified mapping; in a real scenario, we'd use names(cls_id)
                label = res.names[cls_id]
                if conf > 0.5:
                    detected_symbols.append({'sym': label, 'x': float(box.xywh[0][0]), 'conf': conf})

    if not detected_symbols:
        return ocr_text

    # 2. Logic to merge detected symbols into OCR text
    # Sort detected symbols by x-coordinate (left to right)
    detected_symbols.sort(key=lambda x: x['x'])
    
    corrected_text = ocr_text
    
    # Heuristic Correction:
    # A. If Ø detected at the far left and missing in OCR
    if any(s['sym'] == 'Ø' for s in detected_symbols[:2]) and 'Ø' not in ocr_text.upper() and 'Φ' not in ocr_text:
        corrected_text = "Ø" + corrected_text

    # B. If ± detected but OCR has '+' or '9' or '4' in its place
    if any(s['sym'] == '±' for s in detected_symbols):
        if '±' not in ocr_text:
            # If OCR has ' 0.' or ' .', it might be missing the ±
            corrected_text = re.sub(r'\s+([\d\.])', r' ±\1', corrected_text)
            # If no ± after space, just ensure one ± exists if we found it
            if '±' not in corrected_text:
                # Try to insert before the second number
                parts = re.split(r'(\s+)', corrected_text)
                if len(parts) >= 3:
                    corrected_text = parts[0] + " ±" + "".join(parts[2:])

    # C. Digit Recovery (Example: 0.17 -> 5.17)
    # If a digit is detected far left and OCR is missing it
    leftmost_digit = next((s for s in detected_symbols if s['sym'].isdigit()), None)
    if leftmost_digit and not ocr_text.startswith(leftmost_digit['sym']):
        # Only prepend if it looks like a missing leading digit (e.g. OCR starts with .)
        if ocr_text.startswith('.') or (len(ocr_text) > 0 and not ocr_text[0].isdigit() and ocr_text[1] == '.'):
            corrected_text = leftmost_digit['sym'] + corrected_text

    # 3. Validation / Normalization
    corrected_text = corrected_text.replace('  ', ' ').strip()
    
    print(f"[OCR] Original: {original_text}")
    print(f"[SYMBOL] Detected: {[s['sym'] for s in detected_symbols]}")
    print(f"[FINAL] Corrected: {corrected_text}")
    
    return corrected_text

def multi_pass_ocr_validation(cv_img):
    """
    Step 9: Run OCR on multiple preprocessed versions and choose the best one.
    Uses: Original, Sharpened, Threshold images.
    """
    from .paddle_engine import run_paddle_ocr
    
    results = []
    
    # 1. Original
    tokens1 = run_paddle_ocr(cv_img)
    txt1 = " ".join([t['text'] for t in tokens1])
    conf1 = sum([t['confidence'] for t in tokens1]) / len(tokens1) if tokens1 else 0
    results.append({'text': txt1, 'conf': conf1, 'source': 'original'})
    
    # 2. Sharpened
    gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
    kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
    sharpened = cv2.filter2D(gray, -1, kernel)
    sharpened_bgr = cv2.cvtColor(sharpened, cv2.COLOR_GRAY2BGR)
    tokens2 = run_paddle_ocr(sharpened_bgr)
    txt2 = " ".join([t['text'] for t in tokens2])
    conf2 = sum([t['confidence'] for t in tokens2]) / len(tokens2) if tokens2 else 0
    results.append({'text': txt2, 'conf': conf2, 'source': 'sharpened'})
    
    # 3. Threshold (Step 8)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    thresh_bgr = cv2.cvtColor(thresh, cv2.COLOR_GRAY2BGR)
    tokens3 = run_paddle_ocr(thresh_bgr)
    txt3 = " ".join([t['text'] for t in tokens3])
    conf3 = sum([t['confidence'] for t in tokens3]) / len(tokens3) if tokens3 else 0
    results.append({'text': txt3, 'conf': conf3, 'source': 'threshold'})
    
    # Selection logic:
    # 1. Prefer results with digits
    # 2. Prefer results with engineering symbols
    # 3. Higher confidence
    
    def score_result(res):
        text = res['text']
        score = res['conf']
        if any(c.isdigit() for c in text): score += 0.5
        if any(c in text for c in ['Ø', '±', 'R', '°']): score += 0.3
        return score

    best_res = max(results, key=score_result)
    return best_res['text'], best_res['conf']

def run_advanced_ocr_pipeline(crop_img):
    """
    Combined pipeline: Multi-pass OCR -> Symbol Helper Correction
    """
    # 1. Multi-pass OCR
    raw_text, conf = multi_pass_ocr_validation(crop_img)
    
    # 2. Symbol Helper Correction
    corrected_text = detect_and_correct_symbols(crop_img, raw_text)
    
    return corrected_text, conf
