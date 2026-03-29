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

logger = logging.getLogger(__name__)
from .paddle_engine import run_paddle_ocr
from .grouping_engine import group_tokens
from .dimension_parser import extract_and_parse_dimensions
from .dimension_validator import validate_dimension_candidates
from .tolerance_parser import parse_tolerance
from pdf2image import convert_from_path


# ---------------------------------------------------------------------------
# Strict dimension regex — must match the WHOLE (stripped) text or the
# dominant portion of it.  Notes like "Part to be free of cracks..." will
# never match this.
# ---------------------------------------------------------------------------
_DIM_REGEXES = [
    # Ø / R / M prefix: Ø10, R5.5, M8, 4×Ø10
    r'^(?:\d+[×xX]\s*)?[ØRΦøM]\s*\d+(?:[.,]\d+)?(?:\s*[±\+]\s*\d+(?:[.,]\d+)?)?$',

    # Value ± tolerance: 25.4 ± 0.05
    r'^\d+(?:[.,]\d+)?\s*[±\+]\s*\d+(?:[.,]\d+)?$',

    # Dual tolerance: 25.4 +0.1/-0.2
    r'^\d+(?:[.,]\d+)?\s*[+]\d+(?:[.,]\d+)?\s*/\s*-\d+(?:[.,]\d+)?$',

    # Angle: 45° or 103.9°
    r'^\d+(?:[.,]\d+)?\s*°$',

    # Plain decimal: 25.4 or 0.5 (not an integer alone – too ambiguous)
    r'^\d+[.,]\d+$',

    # Integer ≥ 2 digits (e.g. 50, 250) with optional units
    r'^\d{2,}(?:\s*(?:mm|in))?$',

    # THK spec: 1.0 THK or 0.5mm THK
    r'^\d+(?:[.,]\d+)?\s*(?:mm|in)?\s*THK$',

    # Generic dimension with prefix/suffix: 4x Ø10 TYP, 2 HOLES R5
    r'^(?:\d+\s*[xX]\s*|[ØRΦøM]\s*)?\d+(?:[.,]\d+)?(?:\s*[±\+]\s*\d+(?:[.,]\d+)?)?\s*(?:TYP|MAX|MIN|REF|THK|PLCS|HOLES|HOLE|SQ)*$',

    # Dimensions separated by 'x' or '*' e.g. 50x30, 10*20
    r'\d+(?:\.\d+)?\s*[xX*×]\s*\d+(?:\.\d+)?',

    # Reference dims in parens or brackets: (50.0), [50.0]
    r'^[(\[]\s*\d+(?:[.,]\d+)?\s*[)\]]$',
]

# Combine into one pattern that tries each
_COMBINED = re.compile(
    '|'.join(f'(?:{p})' for p in _DIM_REGEXES),
    re.IGNORECASE
)

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
    # Reject long strings (dimension callouts are almost never > 6 words)
    words = t.split()
    if len(words) >= 7:
        return False
    
    # Try strict pattern match first
    if _COMBINED.match(t):
        return True
    
    # Relaxed: short text where majority is numeric/symbol
    # We remove expected symbols and check if anything alphabetic is left
    alpha_only = re.sub(r'[\d\s\.\+\-±°ØRΦøM×x/()\[\]]', '', t)
    # Remove common abbreviations from the alpha check
    for abbr in ['TYP', 'MAX', 'MIN', 'THK', 'PLCS', 'PLS', 'SQ', 'REF', 'HOLES', 'HOLE']:
        alpha_only = re.sub(rf'\b{abbr}\b', '', alpha_only, flags=re.IGNORECASE)

    num_digits = sum(c.isdigit() for c in t)
    
    # Permissive density check
    if len(words) <= 5 and num_digits >= 1 and len(alpha_only) <= 6:
        return True
        
    return False


def detect_bounding_boxes(pdf_path: str) -> list:
    """
    Main entry.  Returns list of bbox dicts for the frontend canvas.
    """
    try:
        pages = convert_from_path(pdf_path, dpi=200)
        if not pages:
            return []
        pil_image = pages[0]
        img_w, img_h = pil_image.size

        if has_vector_text(pdf_path):
            return _detect_vector(pdf_path, img_w, img_h)
        else:
            return _detect_ocr(pdf_path, img_w, img_h, pil_image)

    except Exception as e:
        import traceback
        print(f"[BBox Detector] Error: {e}")
        traceback.print_exc()
        return []


# ---------------------------------------------------------------------------
# Vector path
# ---------------------------------------------------------------------------

def _detect_vector(pdf_path: str, img_w: int, img_h: int) -> list:
    tokens = extract_vector_text(pdf_path, dpi=200)
    if not tokens:
        return []

    # ----- Heading / exclusion zones -----
    # Title block: bottom-right corner
    TB_Y = img_h * 0.80   # title block starts at 80% height
    TB_X = img_w * 0.60   # right 40% 
    # Notes block: bottom-left
    NOTES_Y = img_h * 0.75
    NOTES_X = img_w * 0.45

    # ----- Font-size threshold -----
    # Relaxed: dimensions can be smaller than we think. 
    # Only filter out absolute micro-text (revision clouds, title block fine print).
    sizes = [t['size'] for t in tokens if t['size'] > 0]
    if sizes:
        sizes.sort()
        # Use a more permissive percentile for reference
        ref_size = sizes[int(len(sizes) * 0.4)]
        min_size = ref_size * 0.45
    else:
        min_size = 0

    print(f"[Vector] tokens={len(tokens)}, min_allowed_size={min_size:.2f}")

    results = []
    seen = set()

    for i, tok in enumerate(tokens):
        text = tok['text'].strip()
        x0, y0, x1, y1 = tok['bbox']
        fsize = tok['size']
        direction = tok.get('dir', (1, 0))  # (1,0)=normal, (0,-1)=90° CCW

        # --- Exclusion zones ---
        in_title_block = (y0 > TB_Y and x0 > TB_X)
        in_notes_block = (y0 > NOTES_Y and x0 < NOTES_X)
        if in_title_block or in_notes_block:
            continue

        # --- Font size filter ---
        if fsize > 0 and fsize < min_size:
            continue

        # --- Strict dimension pattern ---
        if not _is_clean_dimension(text):
            continue

        # Deduplicate
        key = (round(x0), round(y0), text)
        if key in seen:
            continue
        seen.add(key)

        # Detect rotation: direction (0, ±1) = vertical text
        is_vertical = abs(direction[0]) < 0.3

        # Parse dimension
        parsed = parse_tolerance(text)

        # Ensure minimum visible box size (vertical text has a thin native bbox)
        MIN_BOX = 30
        w = max(float(x1 - x0), MIN_BOX)
        h = max(float(y1 - y0), MIN_BOX)

        results.append({
            'id':        f'box_v_{i}',
            'serial':    len(results) + 1,
            'x':         float(x0),
            'y':         float(y0),
            'width':     w,
            'height':    h,
            'text':      text,
            'dim':       parsed['dim'],
            'utol':      parsed['utol'],
            'ltol':      parsed['ltol'],
            'vertical':  is_vertical,
            'method':    'vector',
        })

    print(f"[Vector] Detected {len(results)} clean dimensions")
    return results


def _detect_ocr(pdf_path: str, img_w: int, img_h: int, pil_image) -> list:
    # Convert PIL to CV image (BGR) for PaddleOCR
    cv_img = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
    tokens = run_paddle_ocr(cv_img)
    if not tokens:
        return []

    candidates = group_tokens(tokens)
    valid_candidates, noise = validate_dimension_candidates(candidates, img_w, img_h)
    structured = extract_and_parse_dimensions(valid_candidates, img_w, img_h)

    results = []
    for i, d in enumerate(structured):
        x0, y0, x1, y1 = d['bbox']
        results.append({
            'id':     f'box_ocr_{i}',
            'serial': len(results) + 1,
            'x':      float(x0),
            'y':      float(y0),
            'width':  float(x1 - x0),
            'height': float(y1 - y0),
            'text':   d['original'],
            'dim':    d['dim'],
            'utol':   d['utol'],
            'ltol':   d['ltol'],
            'method': 'ocr',
        })
    print(f"[OCR] Detected {len(results)} dimensions (filtered {noise} noise)")
    return results
