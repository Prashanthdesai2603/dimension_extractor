import re
from .dimension_detector import COMBINED_PATTERN
from .tolerance_parser import parse_tolerance

def extract_and_parse_dimensions(candidates: list, img_width: int = 0, img_height: int = 0) -> list:
    """
    Filters candidates for dimensions and parses them into structured objects.
    Ensures that we only return candidates that look like real dimensions.
    """
    # Strict noise keywords list to reject entire blocks
    NOISE_KEYWORDS = [
        'TITLE', 'DWG NO', 'SCALE', 'MATERIAL', 'REV', 'SHEET', 
        'DRAWN', 'CHECKED', 'APPROVED', 'DATE', 'WEIGHT',
        'SIZE', 'DO NOT', 'COPYRIGHT', 'TOLERANCES', 'UNLESS',
        'OTHERWISE', 'SPECIFIED', 'METRIC', 'INCH', 'MM',
        'VIEW', 'ISOMETRIC', 'NOT TO SCALE', 'CAD MODEL', 'BASIC'
    ]
    
    structured_results = []
    
    for cand in candidates:
        text = cand['text'].strip()
        bbox = cand['bbox']
        
        # 1. Basic Noise Filter (Reject if block contains these words)
        text_upper = text.upper()
        if any(kw in text_upper for kw in NOISE_KEYWORDS):
            continue

        # 2. Pattern Match Check
        # We look for the strongest dimension pattern match
        match = re.search(COMBINED_PATTERN, text, re.IGNORECASE)
        
        if match:
            dim_candidate = match.group(0).strip()
            
            # 3. Digit Presence or prefix symbol check
            if not any(char.isdigit() for char in dim_candidate):
                continue
            
            # Additional check: If it has too many words and NO prefix symbol, ignore it
            # e.g. "PART NUMBER 123" should be ignored, but "Ø10" should stay.
            words = text.split()
            if len(words) > 3 and not any(sym in text for sym in ['Ø', 'R', 'Φ', 'ø', 'M', '±', '°']):
                # Too many words, likely not a dimension callout
                continue

            # 4. Parse components using improved tolerance_parser
            parsed = parse_tolerance(text) # Pass full text to let parser find the best part
            
            structured_results.append({
                'original': text,
                'dim': parsed['dim'],
                'utol': parsed['utol'],
                'ltol': parsed['ltol'],
                'bbox': bbox
            })
            
    return structured_results
