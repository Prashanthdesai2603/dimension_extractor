import re
from .dimension_detector import COMBINED_PATTERN
from .tolerance_parser import parse_tolerance

def extract_and_parse_dimensions(candidates: list, img_width: int = 0, img_height: int = 0) -> list:
    """
    Filters candidates for dimensions and parses them into structured objects.
    Redesigned to be inclusive of all dimension types and orientations.
    """
    # Keep noise keywords but reduce them to essentials
    NOISE_KEYWORDS = [
        'TITLE', 'DWG NO', 'SCALE', 'MATERIAL', 'REV', 'SHEET', 
        'DRAWN', 'CHECKED', 'APPROVED', 'DATE', 'WEIGHT',
        'SIZE', 'DO NOT SCALE', 'COPYRIGHT'
    ]
    
    structured_results = []
    
    for cand in candidates:
        text = cand['text'].strip()
        bbox = cand['bbox']
        
        # 1. Noise Keyword Check
        if any(kw in text.upper() for kw in NOISE_KEYWORDS):
            continue

        # 2. Pattern Match Check (Main Classification)
        # We look for ANY dimension pattern in the combined text
        match = re.search(COMBINED_PATTERN, text, re.IGNORECASE)
        
        if match:
            # We take the found match or the whole text if it's primary dimension-like
            dim_text = match.group(0).strip()
            
            # --- REDUCED FILTERING ---
            # We no longer discard based on location (title block) 
            # or aspect ratio unless it's extremely unlikely to be a dimension.
            
            # 3. Basic Validation: must contain at least one digit
            if not any(char.isdigit() for char in dim_text):
                continue

            # 4. Parse into components
            parsed = parse_tolerance(dim_text)
            
            structured_results.append({
                'original': text, # Use full text group for context
                'dim': parsed['dim'],
                'utol': parsed['utol'],
                'ltol': parsed['ltol'],
                'bbox': cand['bbox']
            })
            
    return structured_results
