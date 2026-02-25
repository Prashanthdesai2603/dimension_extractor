import re

def parse_tolerance(text: str) -> dict:
    """
    Parses a dimension string into base dimension, upper tolerance, and lower tolerance.
    
    Rules:
    - 10 ± 0.2     -> Dim: 10, UTol: 0.2, LTol: -0.2
    - 10 +0.2/-0.1 -> Dim: 10, UTol: 0.2, LTol: -0.1
    - Ø18 ±0.05    -> Dim: 18, UTol: 0.05, LTol: -0.05
    """
    if not text:
        return {"dim": "0.0", "utol": "0.0", "ltol": "0.0"}

    # Clean text: remove spaces, normalize symbols
    # Keep digits, dots, plus, minus, slash, and ±
    cleaned = text.strip().replace(' ', '')
    
    # 1. Handle Plus/Minus pattern: 10 ± 0.2 or 10+/-0.2
    # Normalize ± or +/-
    pm_pattern = r'([\d\.]+)(?:±|\+/-)\s*([\d\.]+)'
    pm_match = re.search(pm_pattern, cleaned)
    if pm_match:
        return {
            "dim": pm_match.group(1),
            "utol": pm_match.group(2),
            "ltol": f"-{pm_match.group(2)}"
        }

    # 2. Handle Dual Tolerance pattern: 10+0.2/-0.1
    dual_pattern = r'([\d\.]+)\+([\d\.]+)/-([\d\.]+)'
    dual_match = re.search(dual_pattern, cleaned)
    if dual_match:
        return {
            "dim": dual_match.group(1),
            "utol": dual_match.group(2),
            "ltol": f"-{dual_match.group(3)}"
        }

    # 3. Handle simple Dimension (with optional symbol prefix like Ø or R)
    dim_match = re.search(r'[\d\.]+', cleaned)
    if dim_match:
        return {
            "dim": dim_match.group(0),
            "utol": "0.0",
            "ltol": "0.0"
        }

    # Fallback
    return {
        "dim": text,
        "utol": "0.0",
        "ltol": "0.0"
    }

def format_structured_dimension(parsed: dict) -> str:
    """Format parsed dict into requested text string."""
    dim = parsed.get('dim', '0.0')
    utol = parsed.get('utol', '0.0')
    ltol = parsed.get('ltol', '0.0')
    return f"Dim: {dim}; UTol: {utol}; LTol: {ltol}"
