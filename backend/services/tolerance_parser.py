import re


def parse_tolerance(text: str) -> dict:
    """
    Parses a dimension string into base dimension, upper tolerance, and lower tolerance.
    Handles engineering prefixes (Ø, R, M), bracketed dimensions, and common OCR misreads.
    """
    if not text:
        return {"dim": "0", "utol": "0", "ltol": "0"}

    # 1. Normalize String (Upper, generic cleanup)
    raw_text = str(text).upper().replace(' ', '').strip()
    
    # 2. Extract Sl.No if present (e.g. "1) 37.5")
    serial = None
    serial_match = re.match(r'^(\d+)\s*[\)\.]\s*', text)
    if serial_match:
        serial = serial_match.group(1)
        text = str(text[serial_match.end():]).strip() # type: ignore
        raw_text = text.upper().replace(' ', '').strip()

    # 3. Handle Parentheses/Brackets (Reference dimensions)
    # Detect bracketed value but preserve the inner content
    is_ref = False
    if raw_text.startswith('(') and raw_text.endswith(')'):
        is_ref = True
        raw_text = str(raw_text[1:-1]).strip() # type: ignore
    elif raw_text.startswith('[') and raw_text.endswith(']'):
        is_ref = True
        raw_text = str(raw_text[1:-1]).strip() # type: ignore

    # 4. Normalize symbols to '±'
    clean_text = raw_text
    # Handle misreads like '+/-', '+-', '+ -', '+ / -'
    # Also handle the common '9' misread: if we see "NUMBER 9 NUMBER", and the 9 is between them
    variants = ['+/-', '+ / -', '+ -', '+-', '±-', '± -', '±']
    for v in variants:
        clean_text = clean_text.replace(v, '±')
    
    # Special Fix: If text looks like "10.590.2", it's likely "10.5 ± 0.2"
    # We look for a digit-9-digit pattern that isn't part of a decimal
    clean_text = re.sub(r'(\d)\s*9\s*(\d)', r'\1±\2', clean_text)

    # 5. Preserve Prefix (Ø, R, M)
    prefix_match = re.match(r'^([ØRΦøM])', clean_text)
    prefix = prefix_match.group(1) if prefix_match else ""
    if prefix:
        clean_text = str(clean_text[1:]).strip() # type: ignore

    # ----------------------------------------------------------------
    # A. ± pattern: 25.4 ± 0.05
    # ----------------------------------------------------------------
    num_regex = r'(\d+(?:\.\d+)?)'
    pm_match = re.search(num_regex + r'\s*±\s*' + num_regex, clean_text)
    if pm_match:
        dim = pm_match.group(1)
        tol = pm_match.group(2)
        return {
            "dim": f"{prefix}{dim}",
            "utol": tol,
            "ltol": f"-{tol}",
            "serial": serial
        }

    # ----------------------------------------------------------------
    # B. Dual tolerance: 10 +0.1 -0.2
    # ----------------------------------------------------------------
    dual_match = re.search(num_regex + r'\s*[\+]\s*' + num_regex + r'\s*[\-]\s*' + num_regex, clean_text)
    if dual_match:
        return {
            "dim": f"{prefix}{dual_match.group(1)}",
            "utol": dual_match.group(2),
            "ltol": f"-{dual_match.group(3)}",
            "serial": serial
        }

    # ----------------------------------------------------------------
    # C. Bare number or prefix-only
    # ----------------------------------------------------------------
    bare_match = re.search(num_regex, clean_text)
    if bare_match:
        dim = bare_match.group(0)
        # If there's another number later, it might be a missed tolerance
        remaining = str(clean_text[bare_match.end():]) # type: ignore
        second_num = re.search(num_regex, remaining)
        
        if second_num and len(remaining.strip()) < 10:
            # Likely a tolerance that missed the symbol
            return {
                "dim": f"{prefix}{dim}",
                "utol": second_num.group(0),
                "ltol": f"-{second_num.group(0)}",
                "serial": serial
            }
            
        return {
            "dim": f"{prefix}{dim}",
            "utol": "0", "ltol": "0",
            "serial": serial
        }

    # Fallback
    res = str(clean_text[:20]) or "0" # type: ignore
    return {"dim": f"{prefix}{res}", "utol": "0", "ltol": "0", "serial": serial}


def format_structured_dimension(parsed: dict) -> str:
    """Format parsed dict into requested text string."""
    dim    = parsed.get('dim', '0')
    utol   = parsed.get('utol', '0')
    ltol   = parsed.get('ltol', '0')
    # Support multiple possible keys for the serial number
    serial = parsed.get('serial') or parsed.get('ref') or parsed.get('slno') or parsed.get('sno')

    # Ensure LTol has a minus sign if it's not 0 and doesn't have one
    if str(ltol) not in ('0', '-0', '') and not str(ltol).startswith('-'):
        ltol = f"-{ltol}"

    parts = []
    if serial:
        parts.append(f"Sl.No: {serial}")
    
    parts.append(f"Dim: {dim}")
    parts.append(f"UTol: {utol}")
    parts.append(f"LTol: {ltol}")

    return "; ".join(parts)
