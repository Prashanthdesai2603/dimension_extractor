import re


def parse_tolerance(text: str) -> dict:
    """
    Parses a dimension string into base dimension, upper tolerance, and lower tolerance.
    """
    if not text:
        return {"dim": "0", "utol": "0", "ltol": "0"}

    # 1. Normalize String (Upper, generic cleanup)
    raw_text = str(text).upper().strip()
    
    # 2. Normalize symbols to '±'
    clean_text = raw_text
    # Handle misreads like '+/-', '+-', '+ -', '+ / -'
    # Sort by length descending to match longest sequences first
    variants = ['+/-', '+ / -', '+/-', '+ -', '+-', '±-', '± -']
    for v in variants:
        clean_text = clean_text.replace(v, '±')
    
    # 3. Fix fragmented numbers (OCR sometimes inserts spaces: "1 . 5" -> "1.5")
    # This specifically looks for digits around a decimal or ±/+/-
    clean_text = re.sub(r'(\d+)\s*\.\s*(\d+)', r'\1.\2', clean_text)
    clean_text = re.sub(r'([±\+\-])\s*(\d+)', r'\1\2', clean_text)
    
    # Remove prefix multipliers like "2X", "4x"
    clean_text = re.sub(r'^\d+\s*[X]\s*', '', clean_text)
    
    # Remove brackets/parentheses
    clean_text = re.sub(r'[()\\[\\]]', '', clean_text)

    # ----------------------------------------------------------------
    # A. ± pattern: 25.4 ± 0.05
    # ----------------------------------------------------------------
    # Look for a number followed by ± or + and another number
    pm_regex = r'([ØRΦØM]?\d+(?:\.\d+)?)\s*[±\+]\s*(\d+(?:\.\d+)?)'
    pm_match = re.search(pm_regex, clean_text)
    if pm_match:
        # Check if there's a minus later (might be dual tolerance)
        remaining = clean_text[pm_match.end(1):]
        if '+' in pm_match.group(0) and '-' in remaining and re.search(r'\-\d', remaining):
            pass # let dual_pattern catch it
        else:
            return {
                "dim":  pm_match.group(1).strip(),
                "utol": pm_match.group(2).strip(),
                "ltol": f"-{pm_match.group(2).strip()}",
            }

    # ----------------------------------------------------------------
    # B. Dual tolerance: 10 +0.1 / -0.2
    # ----------------------------------------------------------------
    dual_regex = r'([ØRΦØM]?\d+(?:\.\d+)?)\s*[+]\s*(\d+(?:\.\d+)?)\s*/?\s*[-]\s*(\d+(?:\.\d+)?)'
    dual_match = re.search(dual_regex, clean_text)
    if dual_match:
        return {
            "dim":  dual_match.group(1).strip(),
            "utol": dual_match.group(2).strip(),
            "ltol": f"-{dual_match.group(3).strip()}".replace('--', '-'),
        }

    # ----------------------------------------------------------------
    # C. Simple numeric with engineering prefix (R, Ø, M)
    # ----------------------------------------------------------------
    # Allow optional space: "R 10.5", "Ø 12"
    prefix_regex = r'([ØRΦøM]\s*\d+(?:\.\d+)?)'
    prefix_match = re.search(prefix_regex, clean_text)
    if prefix_match:
        return {
            "dim":  prefix_match.group(1).strip().replace(' ', ''),
            "utol": "0", "ltol": "0",
        }

    # ----------------------------------------------------------------
    # D. Bare number
    # ----------------------------------------------------------------
    # Find all numeric candidates (decimals first, then integers)
    bare_nums = re.findall(r'(\d+(?:\.\d+)?)', clean_text)
    if bare_nums:
        # Prefer the best candidate:
        # 1. Anything with a decimal point is likely a dimension
        # 2. Longer numbers are likely dimensions (serials are usually 1-2 digits)
        # 3. Else pick the first one
        decimals = [n for n in bare_nums if '.' in n]
        if decimals:
            best_bare = decimals[0]
        else:
            # Sort by length descending to pick longest integer
            best_bare = max(bare_nums, key=len)
            
        return {
            "dim":  best_bare,
            "utol": "0", "ltol": "0",
        }

    # Fallback
    return {"dim": clean_text[:20] or "0", "utol": "0", "ltol": "0"}


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
