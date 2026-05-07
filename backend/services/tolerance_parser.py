import re

def normalize_ocr_text(text: str) -> str:
    """
    Step 9: OCR Error Correction
    Normalize text: Replace '9' between numbers with '±', '4' with '±', 'O' with '0'.
    """
    # 1. Handle Degree symbol misreads (often 'o' or '*' or '0' at the end of a number)
    # 10o -> 10°
    text = re.sub(r'(\d)\s*[o*]', r'\1°', text)
    
    # 2. Replace 'O' or remaining 'o' with '0'
    text = text.replace('O', '0').replace('o', '0')
    
    # 3. Standardize diameter symbols to 'Ø'
    diag_symbols = ['⌀', 'Φ', 'φ', 'ø']
    for sym in diag_symbols:
        text = text.replace(sym, 'Ø')

    # 4. Replace symbols like '+/-', '+-', '±-', '±'
    variants = ['+/-', '+ / -', '+ -', '+-', '±-', '± -']
    for v in variants:
        text = text.replace(v, '±')

    # 5. Replace '9' or '4' with '±' when it appears between digits or looks like a separator
    # e.g., 10.5 9 0.2 -> 10.5 ± 0.2
    text = re.sub(r'(\d)\s*[94]\s*(\d)', r'\1±\2', text)
    
    return text

def parse_tolerance(text: str) -> dict:
    """
    Parses a dimension string into base dimension, upper tolerance, and lower tolerance.
    Handles engineering prefixes (Ø, R, M), bracketed dimensions, and common OCR misreads.
    """
    if not text:
        return {"dim": "0", "utol": "0", "ltol": "0"}

    # Step 9: Normalize OCR
    text = normalize_ocr_text(text)

    # 1. Basic Cleanup
    raw_text = str(text).upper().replace(' ', '').strip()
    
    # 2. Extract Sl.No if present (e.g. "1) 37.5" or "1. 37.5")
    # We must be careful not to match decimal dimensions like "18.4" as serial "18"
    serial = None
    # Matches "1) ", "(1) ", or "1. " (but not "18.4")
    serial_match = re.match(r'^[\(\[]?(\d{1,3})[\)\]]\s*|^(\d{1,3})\.\s+', text)
    if serial_match:
        # group(1) for "1) ", group(2) for "1. "
        serial = serial_match.group(1) or serial_match.group(2)
        text = text[serial_match.end():].strip()
        raw_text = text.upper().replace(' ', '').strip()

    # 3. Handle Parentheses/Brackets (Reference dimensions)
    is_ref = False
    if raw_text.startswith('(') and raw_text.endswith(')'):
        is_ref = True
        raw_text = raw_text[1:-1].strip()
    elif raw_text.startswith('[') and raw_text.endswith(']'):
        is_ref = True
        raw_text = raw_text[1:-1].strip()

    # 4. Preserve Prefix (Ø, R, M, and variants like 2XR)
    # Support patterns like 2XR1.0, Ø18, R32.0
    prefix_match = re.match(r'^(\d*[X]?[ØRΦø⌀φM])', raw_text)
    prefix = prefix_match.group(1) if prefix_match else ""
    if prefix:
        raw_text = raw_text[len(prefix):].strip()

    # Update num_regex to optionally include degree symbol
    num_regex = r'(\d+(?:\.\d+)?\s*°?)'
    
    # ----------------------------------------------------------------
    # A. ± pattern: 10 ± 0.2
    # ----------------------------------------------------------------
    pm_match = re.search(num_regex + r'\s*±\s*' + num_regex, raw_text)
    if pm_match:
        dim = pm_match.group(1)
        tol = pm_match.group(2)
        final_dim = f"{prefix}{dim}"
        if is_ref: final_dim = f"({final_dim})"
        return {
            "dim": final_dim,
            "utol": tol,
            "ltol": f"-{tol}",
            "serial": serial
        }

    # ----------------------------------------------------------------
    # B. Dual tolerance: 10 +0.1/-0.2 or 10 +0.2 -0.1
    # ----------------------------------------------------------------
    dual_match = re.search(num_regex + r'\s*[\+]\s*' + num_regex + r'[\/\s]*[\-]\s*' + num_regex, raw_text)
    if dual_match:
        dim = dual_match.group(1)
        utol = dual_match.group(2)
        ltol = dual_match.group(3)
        final_dim = f"{prefix}{dim}"
        if is_ref: final_dim = f"({final_dim})"
        return {
            "dim": final_dim,
            "utol": utol,
            "ltol": f"-{ltol}",
            "serial": serial
        }

    # ----------------------------------------------------------------
    # C. Bare number or prefix-only
    # ----------------------------------------------------------------
    bare_match = re.search(num_regex, raw_text)
    if bare_match:
        dim = bare_match.group(0)
        final_dim = f"{prefix}{dim}"
        if is_ref: final_dim = f"({final_dim})"
        
        # Check if there's a second number that might be a tolerance
        remaining = raw_text[bare_match.end():].strip()
        second_num = re.search(num_regex, remaining)
        if second_num and len(remaining) < 10:
            return {
                "dim": final_dim,
                "utol": second_num.group(0),
                "ltol": f"-{second_num.group(0)}",
                "serial": serial
            }
            
        return {
            "dim": final_dim,
            "utol": "0",
            "ltol": "0",
            "serial": serial
        }

    # Fallback
    final_res = f"{prefix}{raw_text[:10]}"
    if is_ref: final_res = f"({final_res})"
    return {"dim": final_res or "0", "utol": "0", "ltol": "0", "serial": serial}

def format_structured_dimension(parsed: dict) -> str:
    """Format parsed dict into requested text string."""
    dim    = parsed.get('dim', '0')
    utol   = parsed.get('utol', '0')
    ltol   = parsed.get('ltol', '0')
    
    # Ensure LTol has a minus sign if it's not 0 and doesn't have one
    if str(ltol) not in ('0', '-0', '', '0.0') and not str(ltol).startswith('-'):
        ltol = f"-{ltol}"

    return f"Dim: {dim}; UTol: {utol}; LTol: {ltol}"
