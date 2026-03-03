"""
vector_engine.py
Extracts text from the PDF vector layer using PyMuPDF.

Two extraction modes:
  extract_vector_text()     – per-LINE tokens (for detection pipeline)
  extract_all_spans()       – per-SPAN tokens (for spatial region lookup)
  find_text_in_region()     – spatial lookup: given a bbox, return the text
                              whose centroid or overlap falls inside it
"""
import fitz  # PyMuPDF


# ---------------------------------------------------------------------------
# Per-line extraction (used by bbox_detector.py for detection)
# ---------------------------------------------------------------------------

def extract_vector_text(pdf_path: str, dpi: int = 200) -> list:
    """
    Extracts text LINES from the vector PDF layer scaled to 'dpi'.
    Each token: { text, bbox, font, size, dir, chars }
    """
    doc   = fitz.open(pdf_path)
    scale = dpi / 72.0
    tokens = []

    if len(doc) == 0:
        doc.close()
        return tokens

    page = doc[0]
    text_dict = page.get_text("rawdict", flags=fitz.TEXT_PRESERVE_WHITESPACE)

    for block in text_dict.get("blocks", []):
        if block.get("type", -1) != 0:
            continue
        for line in block.get("lines", []):
            full_text = "".join(sp["text"] for sp in line.get("spans", [])).strip()
            if not full_text:
                continue

            bx0, by0, bx1, by1 = line["bbox"]
            spans = line.get("spans", [])
            if not spans:
                continue
            dominant = max(spans, key=lambda s: s.get("size", 0))

            tokens.append({
                "text":  full_text,
                "bbox":  (bx0 * scale, by0 * scale, bx1 * scale, by1 * scale),
                "font":  dominant.get("font", ""),
                "size":  dominant.get("size", 0),
                "dir":   line.get("dir", (1, 0)),
                "chars": len(full_text),
            })

    doc.close()
    print(f"[Vector Engine] Lines extracted: {len(tokens)}")
    return tokens


# ---------------------------------------------------------------------------
# Per-span extraction (used by extractor.py for spatial lookup)
# ---------------------------------------------------------------------------

def extract_all_spans(pdf_path: str, dpi: int = 200) -> list:
    """
    Extracts every individual text span from the vector layer.
    Returns list of { text, bbox, size } in 'dpi' pixel space.
    This gives finer granularity for region-based text lookup.
    """
    doc   = fitz.open(pdf_path)
    scale = dpi / 72.0
    spans = []

    if len(doc) == 0:
        doc.close()
        return spans

    page      = doc[0]
    text_dict = page.get_text("rawdict", flags=fitz.TEXT_PRESERVE_WHITESPACE)

    for block in text_dict.get("blocks", []):
        if block.get("type", -1) != 0:
            continue
        for line in block.get("lines", []):
            for sp in line.get("spans", []):
                t = sp.get("text", "").strip()
                if not t:
                    continue
                sx0, sy0, sx1, sy1 = sp["bbox"]
                spans.append({
                    "text": t,
                    "bbox": (sx0 * scale, sy0 * scale,
                             sx1 * scale, sy1 * scale),
                    "size": sp.get("size", 0),
                    "dir":  line.get("dir", (1, 0)),
                })

    doc.close()
    print(f"[Vector Engine] Spans extracted: {len(spans)}")
    return spans


# ---------------------------------------------------------------------------
# Spatial region lookup
# ---------------------------------------------------------------------------

def find_text_in_region(spans: list, rx: float, ry: float,
                        rw: float, rh: float) -> str:
    """
    Given a list of span tokens and a rectangular region (x, y, w, h)
    in the same coordinate space, return the combined text of all spans
    whose CENTER falls inside the region (or has meaningful overlap).

    The combined text of matching spans is returned as a single string.
    """
    rx0, ry0 = rx, ry
    rx1, ry1 = rx + rw, ry + rh

    matches = []
    for sp in spans:
        sx0, sy0, sx1, sy1 = sp["bbox"]
        # Use the span's centroid
        cx = (sx0 + sx1) / 2
        cy = (sy0 + sy1) / 2
        if rx0 <= cx <= rx1 and ry0 <= cy <= ry1:
            matches.append(sp)
        else:
            # Fall back to overlap check (≥ 40% of span area inside region)
            ox = max(0.0, min(rx1, sx1) - max(rx0, sx0))
            oy = max(0.0, min(ry1, sy1) - max(ry0, sy0))
            span_area = max((sx1 - sx0) * (sy1 - sy0), 1)
            if (ox * oy) / span_area >= 0.40:
                matches.append(sp)

    if not matches:
        return ""

    # Sort by read order: top-to-bottom, then left-to-right
    matches.sort(key=lambda s: (round(s["bbox"][1] / 5) * 5, s["bbox"][0]))
    return " ".join(sp["text"] for sp in matches).strip()


# ---------------------------------------------------------------------------
# Convenience check
# ---------------------------------------------------------------------------

def has_vector_text(pdf_path: str) -> bool:
    """Returns True if the PDF has a text layer with meaningful content."""
    try:
        doc  = fitz.open(pdf_path)
        text = ""
        if len(doc) > 0:
            text = doc[0].get_text().strip()
        doc.close()
        return len(text) > 10
    except Exception:
        return False
