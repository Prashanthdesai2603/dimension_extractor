"""
dimension_validator.py
Used by the OCR/raster fallback path to validate grouped token candidates.
"""
import re
from .dimension_detector import is_dimension

# Phrases that definitively mark a text as a label, not a dimension
NOISE_PHRASES = [
    'VIEW', 'NOTE', 'NOTES', 'SCALE', 'SHEET', 'REV', 'DWG', 'SIZE',
    'MATERIAL', 'WEIGHT', 'UNLESS', 'OTHERWISE', 'SPECIFIED', 'DRAWN',
    'CHECKED', 'APPROVED', 'DATE', 'PROJECTION', 'ANGLE', 'ISOMETRIC',
    'SECTION', 'DETAIL', 'PART', 'ZONE', 'DESCRIPTION', 'REVISION',
    'TOLERANCE', 'REFER', 'CAD', 'MODEL', 'BREAK', 'EDGE', 'BURR',
    'SHARP', 'DESIGN', 'TABLE', 'DURABILITY', 'TORQUE', 'POSITION',
    'IDENTIFICATION', 'AUTHORISATION', 'PRODUCTION', 'SEATING',
    'NOT TO SCALE', 'DO NOT', 'COPYRIGHT', 'BASIC', 'FINISH', 'COLOR',
    'COLOUR', 'ENGINEERING', 'INFORMATION', 'FRONT', 'LEFT', 'RIGHT',
    'TOP', 'BOTTOM',
]


def validate_dimension_candidates(candidates: list, img_width: int, img_height: int) -> tuple:
    """
    Filters a list of grouped token candidates, keeping only those that are
    real engineering dimensions.  Returns (valid_list, noise_count).
    """
    valid = []
    noise = 0

    # Exclusion zones
    tb_y = img_height * 0.80   # title block starts here (bottom)
    tb_x = img_width  * 0.60   # title block in right portion
    notes_y = img_height * 0.75
    notes_x = img_width  * 0.45

    for cand in candidates:
        text = str(cand.get('text', '')).strip()
        bbox = cand.get('bbox', [0, 0, 0, 0])
        x0, y0, x1, y1 = bbox

        if not text:
            continue

        t_up = text.upper()

        # 1. Noise-phrase rejection
        if any(ph in t_up for ph in NOISE_PHRASES):
            noise += 1
            continue

        # 2. Exclusion zones
        if (y0 > tb_y and x0 > tb_x) or (y0 > notes_y and x0 < notes_x):
            noise += 1
            continue

        # 3. Word count — dimensions are short (≤ 6 words)
        if len(text.split()) > 6:
            noise += 1
            continue

        # 4. Pattern check
        if not is_dimension(text):
            noise += 1
            continue

        # 5. Box size sanity (avoid huge label blocks)
        bw = x1 - x0
        bh = y1 - y0
        if bw > img_width * 0.35 or bh > img_height * 0.35:
            noise += 1
            continue

        # 6. Must have at least one digit
        if not any(c.isdigit() for c in text):
            noise += 1
            continue

        valid.append(cand)

    return valid, noise