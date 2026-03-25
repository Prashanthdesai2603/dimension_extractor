"""
dimension_detector.py
Strict dimension pattern matching used by the OCR fallback path.
"""
import re

# Helper for matching numbers with possible OCR spaces: "25 . 4" or "25.4"
_NUM = r'\d+(?:\s*[\.]\s*\d+)?'

# Engineering dimension patterns — order matters (most specific first)
DIMENSION_PATTERNS = [
    # 1. Diameter / Radius / Metric prefix e.g. Ø10, R15, Ø 8.5
    rf'(?:\d+[×xX]\s*)?[ØRΦøM]\s*{_NUM}(?:\s*[±\+]\s*{_NUM})?',

    # 2. Value ± tolerance e.g. 25.4 ±0.05, 3.8 ± 0.2
    rf'{_NUM}\s*[±\+]\s*{_NUM}',

    # 3. Dual tolerance e.g. 25.4 +0.1/-0.2
    rf'{_NUM}\s*[+]\s*{_NUM}\s*/\s*[-]\s*{_NUM}',

    # 4. Angle e.g. 45° 103.9°
    rf'{_NUM}\s*°',

    # 5. Decimal number with possible OCR spaces e.g. "25 . 4"
    rf'\b\d+\s*[\.]\s*\d+\b',

    # 6. Dimensions separated by 'x' or '*' e.g. 50x30, 10*20
    rf'{_NUM}\s*[xX*×]\s*{_NUM}',

    # 7. Integer ≥ 2 digits
    r'\b\d{2,4}\b',

    # 8. Reference dimensions e.g. (50.5), [50.5]
    rf'[(\[]\s*{_NUM}\s*[)\]]',
]

COMBINED_PATTERN = '|'.join(f'(?:{p})' for p in DIMENSION_PATTERNS)


def is_dimension(text: str) -> bool:
    """
    Returns True only if text looks like a real engineering dimension value.
    """
    if not text:
        return False

    t = text.strip()

    # Must have at least one digit
    if not any(c.isdigit() for c in t):
        return False

    # Must match at least one pattern
    if not re.search(COMBINED_PATTERN, t, re.IGNORECASE):
        return False

    # Relaxed: Allow up to 6 words (some dimensions have notes like "TYP 4 ORIENTATIONS")
    if len(t.split()) > 6:
        return False

    # Compute alpha density excluding known engineering symbols and common abbreviations
    # We add common engineering callouts like 'TYP', 'MAX', 'MIN', 'THK', 'PLCS'
    stripped = re.sub(r'[\d\s\.\+\-±°ØRΦøM×x/()\[\]]', '', t)
    # Remove common abbreviations from the alpha check
    for abbr in ['TYP', 'MAX', 'MIN', 'THK', 'PLCS', 'PLS', 'SQ', 'REF', 'HOLES', 'HOLE']:
        stripped = re.sub(rf'\b{abbr}\b', '', stripped, flags=re.IGNORECASE)
    
    digit_count = sum(c.isdigit() for c in t)

    # More permissive alpha density: Allow more text as long as there are digits
    if len(stripped) > 6 and len(stripped) > (digit_count * 1.5):
        return False

    return True


def get_dimension_match(text: str):
    """Extracts the first dimension-like substring from text."""
    m = re.search(COMBINED_PATTERN, text, re.IGNORECASE)
    return m.group(0).strip() if m else None
