import re

# Refined dimension patterns to catch ALL engineering dimensions
DIMENSION_PATTERNS = [
    # Pattern 1: Diameter/Radius/Metric/Count (e.g., Ø25.4, R10, M8, 4x Ø10, 2-R5)
    r'(?:\d+[\-x]\s*)?[ØRΦøM]\s*[0-9]+(?:\.[0-9]+)?',
    
    # Pattern 2: Value with tolerance (e.g. 25.4 ± 0.05, 25.4 +0.1/-0.2, 10 +0.1 0)
    r'\d+(?:\.\d+)?\s*(?:[±\+\-]|(?:\+\s*\d+(?:\.\d+)?\s*/\s*-\s*\d+(?:\.\d+)?))\s*\d+(?:\.\d+)?',
    
    # Pattern 3: Fractional dimensions or Inch symbols (e.g. 1/2, 3/4, 5.0")
    r'\d+(?:\s*/\s*\d+|["\'])',
    
    # Pattern 4: Degrees and Angles (e.g. 45°, 90.5°, 30.0 °)
    r'\d+(?:\.\d+)?\s*(?:[°°]|deg)',
    
    # Pattern 5: Decimal number (e.g. 25.4, .5, 100.0)
    r'(?:\d+)?\.\d+',
    
    # Pattern 6: Integer dimension (allow any integer, weeding out noise later if needed)
    r'\b\d+\b',
]

# Combined pattern for matching
# We use case-insensitive and allow symbols
COMBINED_PATTERN = '|'.join(f'(?:{p})' for p in DIMENSION_PATTERNS)

def is_dimension(text: str):
    """
    Checks if the given text matches a dimension pattern.
    """
    if not text:
        return False
    
    # Clean text: remove common noise but keep symbols
    clean_text = text.strip()
    
    # Check if there's any dimension pattern present
    match = re.search(COMBINED_PATTERN, clean_text, re.IGNORECASE)
    return bool(match)

def get_dimension_match(text: str):
    """
    Extracts the first dimension-like substring from text.
    """
    match = re.search(COMBINED_PATTERN, text, re.IGNORECASE)
    if match:
        return match.group(0).strip()
    return None
