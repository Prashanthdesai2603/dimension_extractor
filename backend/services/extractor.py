"""
extractor.py
============

Extract dimension values from user-drawn bounding boxes.

Processing priority for each bounding box:
  1. FAST PATH      — box already carries text/dim from the auto-detector
                      (the bbox arrived pre-annotated by bbox_detector.py).
                      Parse directly, no re-extraction needed.
  2. VECTOR LOOKUP  — box is manual (or text is blank) AND the PDF has a
                      vector text layer.  Use PyMuPDF spatial search for
                      100% accurate extraction from CAD/vector PDFs.
  3. OCR FALLBACK   — PDF has no vector text (scanned/raster) or vector
                      lookup found nothing.  Crop the image, run PaddleOCR with
                      multi-orientation trial (0°, 90°, 180°, 270°) and 
                      intelligent dimension pattern selection.
                      Supports targeted 'horizontal' or 'vertical' extraction
                      modes for 100% precision.
  4. PLACEHOLDER    — manual box where everything failed.  Return an empty
                      row so the user can type the value themselves.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

import fitz          # PyMuPDF
import numpy as np

from .dimension_detector import get_dimension_match, is_dimension
from .dimension_extractor import detect_vector_text, extract_dimension_value
from .model_loader import get_paddle_ocr
from .tolerance_parser import parse_tolerance
from .vector_engine import extract_all_spans, find_text_in_region

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result builders
# ---------------------------------------------------------------------------

def _make_result(rid: Any, serial: Any, text: str, is_manual: bool) -> Dict[str, Any]:
    """Parse raw text into dim/utol/ltol and build a standard result dict."""
    parsed = parse_tolerance(text)
    status = "MANUAL" if is_manual else "AUTO"
    return {
        "id":        rid,
        "serial":    serial,
        "dim":       parsed["dim"],
        "utol":      parsed["utol"],
        "ltol":      parsed["ltol"],
        "original":  text,
        "is_manual": is_manual,
        "status":    status,
    }


def _make_result_manual(rid: Any, serial: Any, text: str) -> Dict[str, Any]:
    """
    Result builder for manual boxes.

    Strips any leading serial-index text that may have ended up in the OCR
    output (e.g. "1 25.4" → "25.4"), then parses dim/utol/ltol.
    """
    text = str(text or "").strip()

    # Strip leading serial-index tokens: "1 ...", "(1) ...", "1: ...", "1. ..."
    if serial:
        s_str = str(serial)
        patterns = [
            rf"^{s_str}\s+",        # "1 ..."
            rf"^\({s_str}\)\s*",    # "(1) ..."
            rf"^\[{s_str}\]\s*",    # "[1] ..."
            rf"^{s_str}[:.-]\s*",   # "1: ..." / "1. ..."
            rf"\b{s_str}$",         # "... 1"
        ]
        temp = text
        for p in patterns:
            temp = re.sub(p, "", temp, flags=re.IGNORECASE).strip()
        if any(c.isdigit() for c in temp):
            text = temp

    parsed = parse_tolerance(text)

    if parsed["dim"] and any(c.isdigit() for c in str(parsed["dim"])):
        return {
            "id":        rid,
            "serial":    serial,
            "dim":       str(parsed["dim"]),
            "utol":      str(parsed["utol"]),
            "ltol":      str(parsed["ltol"]),
            "original":  text,
            "is_manual": True,
            "status":    "MANUAL",
        }

    # Absolute fallback: return raw text so the user sees something
    return {
        "id":        rid,
        "serial":    serial,
        "dim":       text,
        "utol":      "0",
        "ltol":      "0",
        "original":  text,
        "is_manual": True,
        "status":    "MANUAL",
    }


def _make_placeholder(rid: Any, serial: Any) -> Dict[str, Any]:
    """Empty row for a manual box where all extraction failed."""
    return {
        "id":        rid,
        "serial":    serial,
        "dim":       "",
        "utol":      "0",
        "ltol":      "0",
        "original":  "",
        "is_manual": True,
        "status":    "LOW_CONF",
    }


def _result_from_hybrid(
    rid: Any,
    serial: Any,
    hybrid: Dict[str, Any],
    is_manual: bool,
) -> Dict[str, Any]:
    """
    Build a result dict from the output of ``extract_dimension_value()``.
    The hybrid dict already carries dim/utol/ltol from tolerance_parser.
    """
    conf = hybrid.get("conf", 0.0)
    status = "AUTO"
    if is_manual:
        status = "MANUAL"
    elif conf < 0.6 and conf > 0:
        status = "LOW_CONF"

    return {
        "id":        rid,
        "serial":    serial,
        "dim":       hybrid.get("dim", ""),
        "utol":      hybrid.get("utol", "0"),
        "ltol":      hybrid.get("ltol", "0"),
        "original":  hybrid.get("text", ""),
        "is_manual": is_manual,
        "method":    hybrid.get("method", "none"),
        "conf":      conf,
        "status":    status,
    }


# ---------------------------------------------------------------------------
# AABB helper for rotated boxes
# ---------------------------------------------------------------------------

def _rotated_aabb(
    x: float, y: float, w: float, h: float, rot_deg: float
) -> Tuple[float, float, float, float]:
    """
    Return the axis-aligned bounding box of a rectangle rotated around its
    top-left corner by ``rot_deg`` degrees.

    Returns (x0, y0, w_aabb, h_aabb).
    """
    rad = np.radians(rot_deg)
    cos_a, sin_a = np.cos(rad), np.sin(rad)
    corners = [(0.0, 0.0), (w, 0.0), (w, h), (0.0, h)]
    pts = [(x + cx * cos_a - cy * sin_a, y + cx * sin_a + cy * cos_a)
           for cx, cy in corners]
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    x0, y0 = min(xs), min(ys)
    return x0, y0, max(xs) - x0, max(ys) - y0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_dimensions_from_bboxes(pdf_path: str, rectangles: list, viewer_context: dict = None, orientation: str = None) -> list:
    """
    Extract dimension values from a list of bounding boxes.

    ``rectangles``
        List of dicts with the following optional keys::

            id, x, y, width, height   — required geometry (200-DPI pixels)
            rotation                  — rotation angle in degrees (default 0)
            text, dim, utol, ltol     — pre-annotated values from auto-detector
            method                    — "manual" if user drew the box
            serial                    — integer label shown on the canvas

    Returns a list of result dicts sorted by serial number.
    """
    if not rectangles:
        return []

    # -----------------------------------------------------------------------
    # Split: fast-path (already have text) vs lookup-queue (needs extraction)
    # -----------------------------------------------------------------------
    fast_results: List[Dict[str, Any]] = []
    lookup_queue: List[Tuple[Dict[str, Any], bool]] = []  # (rect, is_manual)

    for rect in rectangles:
        known_text = str(rect.get("text", "") or "").strip()
        known_dim  = str(rect.get("dim",  "") or "").strip()
        serial     = rect.get("serial")
        is_manual  = (rect.get("method") == "manual") or (known_text in ("", "Manual"))

        if not is_manual and known_text and any(c.isdigit() for c in known_text):
            # ---- FAST PATH: pre-annotated by bbox_detector ----
            parsed = parse_tolerance(known_text)
            if known_dim and known_dim not in ("", "0", "null", "undefined", "None"):
                parsed["dim"] = known_dim
            utol = str(rect.get("utol", "0") or "0").strip()
            ltol = str(rect.get("ltol", "0") or "0").strip()
            if utol not in ("", "0", "null", "undefined", "None"):
                parsed["utol"] = utol
            if ltol not in ("", "0", "null", "undefined", "None"):
                parsed["ltol"] = ltol
            fast_results.append({
                "id":        rect.get("id"),
                "serial":    serial,
                "dim":       parsed["dim"],
                "utol":      parsed["utol"],
                "ltol":      parsed["ltol"],
                "original":  known_text,
                "is_manual": False,
                "method":    "vector",
                "conf":      1.0,
            })
        else:
            lookup_queue.append((rect, is_manual))

    logger.info(
        "[Extractor] Fast=%d  Lookup-queue=%d",
        len(fast_results), len(lookup_queue),
    )

    if not lookup_queue:
        return fast_results

    # -----------------------------------------------------------------------
    # VECTOR LAYER — load all spans once (PyMuPDF)
    # -----------------------------------------------------------------------
    vector_spans: List[Dict[str, Any]] = []
    has_vector = detect_vector_text(pdf_path)
    if has_vector:
        try:
            vector_spans = extract_all_spans(pdf_path, dpi=200)
            logger.info("[Extractor] Vector spans loaded: %d", len(vector_spans))
        except Exception as exc:
            logger.warning("[Extractor] Vector span load error: %s", exc)

    # -----------------------------------------------------------------------
    # Process each lookup box
    # -----------------------------------------------------------------------
    results: List[Dict[str, Any]] = []
    ocr_model = None
    doc = None

    try:
        doc = fitz.open(pdf_path)
        page = doc[0] if len(doc) > 0 else None

        if viewer_context:
            logger.info("[Extractor] Received viewer_context: %s", viewer_context)

        for rect, is_manual in lookup_queue:
            rid    = rect.get("id")
            serial = rect.get("serial")

            # Parse geometry
            try:
                # 1. Start with frontend coordinates (200 DPI space by default)
                x_200 = float(rect.get("x",      0))
                y_200 = float(rect.get("y",      0))
                w_200 = float(rect.get("width",  50))
                h_200 = float(rect.get("height", 20))
                rot   = float(rect.get("rotation", 0) or 0)

                # 2. Dynamic Scaling Check:
                # If viewer_context is provided, we can verify if the frontend's 
                # coordinate system (e.g. 200 DPI) matches our expectation.
                if viewer_context:
                    # pdf_w_pts = viewer_context.get('pdfWidth')
                    # viewer_w_px = viewer_context.get('viewerWidth')
                    # Here we assume frontend always sends coordinates at 200 DPI scale
                    # and we don't need additional scaling unless viewer_context 
                    # indicates a different target.
                    pass

            except (TypeError, ValueError) as exc:
                logger.warning("[Extractor] Bad geometry for box %s: %s", rid, exc)
                if is_manual:
                    results.append(_make_placeholder(rid, serial))
                continue

            # Convert rotated box → AABB for spatial lookup and crop
            if abs(rot) > 0.1:
                x_200, y_200, w_200, h_200 = _rotated_aabb(x_200, y_200, w_200, h_200, rot)
                logger.debug(
                    "[Extractor] Rotated box %s (%.1f°) → AABB x=%.1f y=%.1f w=%.1f h=%.1f",
                    rid, rot, x_200, y_200, w_200, h_200,
                )

            # ----------------------------------------------------------------
            # Unified hybrid extraction: vector-first, OCR fallback
            # ----------------------------------------------------------------
            # Unified hybrid extraction: vector-first, OCR fallback
            # ----------------------------------------------------------------
            ocr_model = get_paddle_ocr()

            # Smart Box Expansion (Requirement 4)
            # padding = max(width, height) * 0.15
            padding_factor = 0.15
            pad_px = max(w_200, h_200) * padding_factor
            
            # Keep a minimum padding for safety (25px ensures we don't clip technical symbols)
            pad_px = max(pad_px, 25.0)

            # Tighter inner expansion for vector spans
            expand_px = 4.0 if is_manual else 8.0

            hybrid = extract_dimension_value(
                pdf_path,
                bbox_200dpi=(x_200, y_200, w_200, h_200),
                page_number=0,
                vector_spans=vector_spans if has_vector else None,
                expand_px_200dpi=expand_px,
                pad_px_200dpi=pad_px,
                page=page,
                ocr_model=ocr_model,
                is_curved=bool(is_manual),
                orientation_hint=orientation if orientation in ["horizontal", "vertical"] else None,
            )

            method = hybrid.get("method", "none")
            text   = hybrid.get("text", "")

            logger.info(
                "[Extractor] box=%s  serial=%s  method=%s  text='%s'  conf=%.2f",
                rid, serial, method, text, hybrid.get("conf", 0.0),
            )

            if text:
                if is_manual:
                    results.append(_make_result_manual(rid, serial, text))
                else:
                    results.append(_result_from_hybrid(rid, serial, hybrid, is_manual=False))
                continue

            # Nothing found → placeholder for manual boxes only
            if is_manual:
                results.append(_make_placeholder(rid, serial))

    finally:
        if doc:
            doc.close()

    final = fast_results + results
    # Preserve the serial-number order shown in the drawing canvas
    final.sort(key=lambda r: (r.get("serial") is None, r.get("serial") or 999))

    logger.info("[Extractor] Completed. Total results: %d", len(final))
    return final
