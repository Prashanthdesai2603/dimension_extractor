"""
dimension_detector.py
Strict dimension pattern matching used by the OCR fallback path.
"""
import re

# Engineering dimension patterns — order matters (most specific first)
DIMENSION_PATTERNS = [
    # 1. Diameter / Radius / Metric prefix  e.g. Ø10, R5.5, M8
    r'(?:\d+[×xX]\s*)?[ØRΦøM]\s*\d+(?:\.\d+)?(?:\s*[±\+]\s*\d+(?:\.\d+)?)?',

    # 2. Value ± tolerance  e.g. 25.4 ± 0.05
    r'\d+(?:\.\d+)?\s*[±\+]\s*\d+(?:\.\d+)?',

    # 3. Dual tolerance  e.g. 25.4 +0.1/-0.2
    r'\d+(?:\.\d+)?\s*[+]\d+(?:\.\d+)?\s*/\s*-\d+(?:\.\d+)?',

    # 4. Angle  e.g. 45°  103.9°
    r'\d+(?:\.\d+)?\s*°',

    # 5. Decimal number  e.g. 25.4
    r'\b\d+\.\d{1,4}\b',

    # 6. Integer ≥ 2 digits (avoid single-digit revision numbers)
    r'\b\d{2,4}\b',
]

COMBINED_PATTERN = '|'.join(f'(?:{p})' for p in DIMENSION_PATTERNS)


def is_dimension(text: str) -> bool:
    """
    Returns True only if text looks like a real engineering dimension value.
    Uses strict criteria:
     - must contain at least one digit
     - must match a dimension pattern
     - must NOT be dominated by alphabetic characters
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

    # Reject if more than 4 words (it's a sentence/label)
    if len(t.split()) > 4:
        return False

    # Compute alpha density excluding known engineering symbols
    stripped = re.sub(r'[\d\s\.\+\-±°ØRΦøM×x/()\[\]]', '', t)
    digit_count = sum(c.isdigit() for c in t)

    # More than 3 non-symbol alpha chars and outnumber digits → label
    if len(stripped) > 3 and len(stripped) > digit_count:
        return False

    return True


def get_dimension_match(text: str):
    """Extracts the first dimension-like substring from text."""
    m = re.search(COMBINED_PATTERN, text, re.IGNORECASE)
    return m.group(0).strip() if m else None
