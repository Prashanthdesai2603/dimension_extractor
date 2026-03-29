"""
dimension_extractor.py
======================

Hybrid (VECTOR + OCR) dimension extraction service.

Priority order for every user-supplied bounding box:
  1. Vector layer lookup  (PyMuPDF — near-perfect accuracy for CAD/vector PDFs)
  2. OCR fallback         (docTR — for scanned/raster PDFs or missing vector text)

This module ONLY handles *value extraction* from bounding boxes.
It does NOT modify or replace the existing automatic dimension-detection
pipeline (bbox_detector.py / pipeline.py).

Public API
----------
detect_vector_text(pdf_path, page_number, min_chars)
    → bool
    STEP 1 — returns True if the page has a meaningful vector text layer.

extract_from_vector(pdf_path, page_number, dpi, only_dimensions)
    → List[{"text": str, "bbox": [x0,y0,x1,y1]}]
    STEP 2 — returns all (or only-dimension) span tokens with pixel bboxes.

extract_with_ocr(pdf_path, bbox_200dpi, page_number, ...)
    → (text: str, confidence: float)
    STEPS 4-6 — high-DPI render + preprocessing + multi-rotation OCR.

extract_dimension_value(pdf_path, bbox_200dpi, ...)
    → {"text": str, "method": "vector"|"ocr"|"none", "conf": float}
    STEPS 3-7 — unified entry point: vector-first, OCR fallback.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

import cv2 # type: ignore
import fitz  # type: ignore # PyMuPDF
import numpy as np # type: ignore

from .dimension_detector import get_dimension_match, is_dimension # type: ignore
from .model_loader import get_paddle_ocr # type: ignore
from .paddle_engine import extract_text_from_region # type: ignore
from .tolerance_parser import parse_tolerance # type: ignore
from .vector_engine import find_text_in_region # type: ignore

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# STEP 1 — Detect whether a PDF page has a vector text layer
# ---------------------------------------------------------------------------

def detect_vector_text(
    pdf_path: str,
    page_number: int = 0,
    min_chars: int = 10,
) -> bool:
    """
    Return True if the PDF page contains a meaningful vector text layer.

    Uses PyMuPDF ``page.get_text("dict")`` and counts characters in text
    blocks (block type == 0).  At least ``min_chars`` non-whitespace
    characters must be found for the page to be considered 'vector'.

    Args:
        pdf_path:    Absolute path to the PDF file.
        page_number: Zero-based page index (default 0).
        min_chars:   Minimum total character count to consider the page
                     as having vector text (default 10).

    Returns:
        True  → vector PDF  (use vector extraction first).
        False → scanned / raster PDF (use OCR fallback).
    """
    try:
        doc = fitz.open(pdf_path)
        try:
            if len(doc) == 0 or page_number < 0 or page_number >= len(doc):
                return False

            page = doc[page_number]
            char_count: int = 0
            text_dict: dict = page.get_text("dict")
            blocks: list = text_dict.get("blocks", [])

            for block in blocks:
                if not isinstance(block, dict): continue
                if block.get("type", -1) != 0:   # 0 = text block
                    continue
                lines: list = block.get("lines", []) or []
                for line in lines:
                    if not isinstance(line, dict): continue
                    spans: list = line.get("spans", []) or []
                    for span in spans:
                        if not isinstance(span, dict): continue
                        t: str = str(span.get("text", "")).strip()
                        if t:
                            char_count += len(t) # type: ignore
                            if char_count >= int(min_chars):
                                return True
            return False
        finally:
            if doc:
                doc.close()
    except Exception as exc:
        logger.warning("[detect_vector_text] Error reading %s: %s", pdf_path, exc)
        return False
    return False # Explicit fallback for linter


# ---------------------------------------------------------------------------
# STEP 2 — Vector text extraction (span-level tokens with pixel bboxes)
# ---------------------------------------------------------------------------

def extract_from_vector(
    pdf_path: str,
    page_number: int = 0,
    dpi: int = 200,
    only_dimensions: bool = True,
) -> List[Dict[str, Any]]:
    """
    Extract text spans from the PDF vector layer, scaled to ``dpi``-pixel space.

    Each returned token::

        {"text": "103.2", "bbox": [x0, y0, x1, y1]}

    Coordinates are in the image pixel space at the given ``dpi``.

    Args:
        pdf_path:         Absolute path to the PDF.
        page_number:      Zero-based page index.
        dpi:              Target DPI for coordinate scaling (must match the
                          viewer's rendering DPI, default 200).
        only_dimensions:  If True, only spans that match a dimension pattern
                          are returned.  If False, all non-empty spans are
                          returned.

    Returns:
        List of span dicts.
    """
    tokens: List[Dict[str, Any]] = []

    try:
        doc = fitz.open(pdf_path)
        try:
            if len(doc) == 0 or page_number < 0 or page_number >= len(doc):
                return []

            page = doc[page_number]
            # PDF coords are in points (1 pt = 1/72 inch)
            scale = float(dpi) / 72.0

            text_dict = page.get_text(
                "rawdict", flags=fitz.TEXT_PRESERVE_WHITESPACE
            )

            blocks_list: list = text_dict.get("blocks", [])
            for block in blocks_list: # type: ignore
                if not isinstance(block, dict): continue
                if block.get("type", -1) != 0:
                    continue
                lines_list: list = block.get("lines", []) or []
                for line in lines_list: # type: ignore
                    if not isinstance(line, dict): continue
                    spans_list: list = line.get("spans", []) or []
                    for sp in spans_list: # type: ignore
                        if not isinstance(sp, dict): continue
                        t = str(sp.get("text", "")).strip()
                        if not t:
                            continue
                        # STEP 2 — filter: only dimension-pattern spans
                        if only_dimensions and not is_dimension(t) and not get_dimension_match(t):
                            continue

                        x0, y0, x1, y1 = sp.get("bbox", (0.0, 0.0, 0.0, 0.0))
                        tokens.append(
                            {
                                "text": t,
                                "bbox": [
                                    x0 * scale,
                                    y0 * scale,
                                    x1 * scale,
                                    y1 * scale,
                                ],
                            }
                        )

            logger.debug(
                "[extract_from_vector] page=%d  spans=%d  (only_dims=%s)",
                page_number, len(tokens), only_dimensions,
            )
            return tokens
        finally:
            doc.close()
    except Exception as exc:
        logger.warning("[extract_from_vector] Error: %s", exc)
        return tokens
    return [] # Explicit fallback for linter


# ---------------------------------------------------------------------------
# STEP 3/4/5/6 — OCR fallback with preprocessing + multi-rotation selection
# ---------------------------------------------------------------------------

def extract_with_ocr(
    pdf_path: str,
    bbox_200dpi: Tuple[float, float, float, float],
    page_number: int = 0,
    *,
    pad_px_200dpi: float = 25.0,
    dpi: Optional[int] = None,
    is_low_res: Optional[bool] = None,
    is_curved: bool = False,
    page: Optional[Any] = None,
    ocr_model: Optional[Any] = None,
    orientation_hint: Optional[str] = None,
) -> Tuple[str, float]:
    """
    STEP 4/5/6 — OCR extraction with high-DPI rendering and multi-rotation.

    Renders the bounding-box region from the PDF at a high DPI, preprocesses
    the crop (CLAHE + upscale), then tries 4 orientations (0°/90°/180°/270°)
    and returns the highest-confidence validated dimension string.

    Args:
        pdf_path:       Absolute path to the PDF.
        bbox_200dpi:    (x, y, w, h) in the viewer's 200-DPI pixel space.
        page_number:    Zero-based page index.
        pad_px_200dpi:  Padding added around the crop in 200-DPI pixels.
        dpi:            Override render DPI.  If None, chosen automatically
                        (500 for small/low-res crops, 300 otherwise).
        is_low_res:     Override low-res heuristic.  If None, inferred from
                        bbox size (w < 80 px or h < 30 px at 200 DPI).
        is_curved:      Enables a gentle Gaussian blur before CLAHE (useful
                        for slightly curved or noisy text).
        page:           Re-usable open PyMuPDF page object (performance).
        ocr_model:      Re-usable loaded docTR model (performance).

    Returns:
        (best_text, confidence) — empty string and 0.0 on failure.
    """
    x_200, y_200, w_200, h_200 = bbox_200dpi
    if w_200 <= 1 or h_200 <= 1:
        return "", 0.0

    # Convert 200-DPI pixels → PDF points (72 DPI)
    s_to_pt = 72.0 / 200.0
    xp  = float(x_200) * s_to_pt
    yp  = float(y_200) * s_to_pt
    wp  = float(w_200) * s_to_pt
    hp  = float(h_200) * s_to_pt
    
    # Feature 2 — SMART BOX EXPANSION
    # Expand the bounding box by 15% of the largest dimension to avoid clipping digits.
    dynamic_pad = max(float(w_200), float(h_200)) * 0.15
    # Use max of fixed padding (25px default) and dynamic padding
    pad_px = max(float(pad_px_200dpi), dynamic_pad)
    pad_pt = pad_px * s_to_pt

    # enough pixels for the OCR model.
    if is_low_res is None:
        is_low_res = (w_200 < 80) or (h_200 < 30)
    render_dpi = int(dpi or (500 if is_low_res else 300))

    owned_doc = None
    try:
        # Open PDF only if no page was supplied
        if page is None:
            owned_doc = fitz.open(pdf_path)
            if len(owned_doc) == 0 or page_number < 0 or page_number >= len(owned_doc):
                return "", 0.0
            page = owned_doc[page_number]

        clip = fitz.Rect(
            xp - pad_pt,
            yp - pad_pt,
            xp + wp + pad_pt,
            yp + hp + pad_pt,
        )
        pix = page.get_pixmap(clip=clip, dpi=render_dpi)

        # Convert PyMuPDF pixmap to NumPy / OpenCV RGB image.
        # PyMuPDF samples are already in RGB order (NOT BGR).
        # Handle 3-channel (RGB) and 4-channel (RGBA) pixmaps.
        img_np = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
            pix.height, pix.width, pix.n
        )

        if pix.n == 4:
            # RGBA → RGB (drop alpha)
            img_rgb = cv2.cvtColor(img_np, cv2.COLOR_RGBA2RGB)
        elif pix.n == 3:
            # PyMuPDF returns RGB; no conversion needed for docTR
            img_rgb = img_np.copy()
        else:
            # Grayscale → RGB
            img_rgb = cv2.cvtColor(img_np, cv2.COLOR_GRAY2RGB)

        img_final = _preprocess_for_paddle(
            img_rgb, is_curved=is_curved, is_low_res=bool(is_low_res)
        )
        return extract_text_from_region(img_final, orientation_hint=orientation_hint)

    except Exception as exc:
        logger.warning("[extract_with_ocr] Error: %s", exc)
        return "", 0.0
    finally:
        if owned_doc is not None:
            owned_doc.close()
    return "", 0.0 # Explicit fallback for linter


# ---------------------------------------------------------------------------
# STEP 3/7 — Unified hybrid entry point
# ---------------------------------------------------------------------------

def extract_dimension_value(
    pdf_path: str,
    bbox_200dpi: Tuple[float, float, float, float],
    *,
    page_number: int = 0,
    vector_spans: Optional[List[Dict[str, Any]]] = None,
    expand_px_200dpi: float = 4.0,
    pad_px_200dpi: float = 25.0,
    is_curved: bool = False,
    ocr_dpi: Optional[int] = None,
    page: Optional[Any] = None,
    ocr_model: Optional[Any] = None,
    force_ocr: bool = False,
    orientation_hint: Optional[str] = None,
) -> Dict[str, Any]:
    """
    STEPS 3–7 — Hybrid extraction for a single user-drawn bounding box.

    Strategy
    --------
    1. **Vector lookup** (STEP 3):
       If ``vector_spans`` are provided and any span lies inside the
       expanded box, return that text immediately — confidence 1.0.
       This gives near-perfect accuracy for CAD vector PDFs.

    2. **OCR fallback** (STEPS 4–6):
       If vector lookup finds nothing, render the region at high DPI,
       apply preprocessing (CLAHE + upscale), try 4 orientations and
       select the highest-confidence validated dimension string.

    3. **Tolerance parsing** (STEP 7):
       The caller may pass the returned ``text`` through
       ``tolerance_parser.parse_tolerance()`` to split dim/utol/ltol.

    Args:
        pdf_path:         Absolute path to the PDF.
        bbox_200dpi:      (x, y, w, h) in 200-DPI viewer pixel space.
        page_number:      Zero-based page index (default 0).
        vector_spans:     Pre-loaded span list from ``extract_from_vector()``
                          or ``vector_engine.extract_all_spans()``.
                          Pass None to skip vector lookup.
        expand_px_200dpi: Extra pixels added on each side of the user box
                          when searching for vector spans (default 4).
        pad_px_200dpi:    Padding (in 200-DPI pixels) for the OCR crop.
        is_curved:        Enable gentle blur in OCR preprocessing.
        ocr_dpi:          Override OCR render DPI.
        page:             Re-usable open PyMuPDF page (performance).
        ocr_model:        Re-usable loaded docTR model (performance).
        force_ocr:        Skip vector lookup and go straight to OCR.

    Returns:
        {
            "text":   "<extracted string or ''>",
            "method": "vector" | "ocr" | "none",
            "conf":   float,           # 1.0 for vector, model conf for OCR
            "dim":    str,             # parsed base dimension
            "utol":   str,             # upper tolerance (0 if none)
            "ltol":   str,             # lower tolerance (0 if none)
        }
    """
    x, y, w, h = bbox_200dpi
    exp = float(expand_px_200dpi)

    # ------------------------------------------------------------------
    # STEP 3 — Vector spatial lookup (skip if forced OCR or no spans)
    # ------------------------------------------------------------------
    if not force_ocr and vector_spans:
        found_raw = find_text_in_region(
            vector_spans,
            float(x) - exp,
            float(y) - exp,
            float(w) + exp * 2.0,
            float(h) + exp * 2.0,
        )
        found = str(found_raw or "").strip()

        if found:
            # Prefer the clean dimension substring if the span contains extras
            if is_dimension(found):
                dim_text = found
            else:
                dim_text = str(get_dimension_match(found) or "").strip() # type: ignore

            if dim_text and is_dimension(dim_text):
                # STEP 7 — parse tolerance components
                parsed = parse_tolerance(dim_text)
                logger.debug(
                    "[hybrid] Vector hit: '%s' inside box (%g,%g,%g,%g)",
                    dim_text, x, y, w, h,
                )
                return {
                    "text":   dim_text,
                    "method": "vector",
                    "conf":   1.0,
                    "dim":    parsed["dim"],
                    "utol":   parsed["utol"],
                    "ltol":   parsed["ltol"],
                }

    # ------------------------------------------------------------------
    # STEPS 4-6 — OCR fallback (Pass 1 - Standard)
    # ------------------------------------------------------------------
    ocr_text, ocr_conf = extract_with_ocr(
        pdf_path,
        bbox_200dpi=bbox_200dpi,
        page_number=page_number,
        pad_px_200dpi=float(pad_px_200dpi),
        dpi=ocr_dpi,
        page=page,
        ocr_model=ocr_model,
        is_curved=bool(is_curved),
        orientation_hint=orientation_hint,
    )
    
    # Validation
    final_text = str(ocr_text or "").strip()
    if not is_dimension(final_text):
        final_text = str(get_dimension_match(final_text) or "").strip() # type: ignore

    # Pass 2 — Lighter preprocessing if Pass 1 yielded no valid dimension or low confidence
    if not final_text or ocr_conf < 0.6:
        logger.debug("[hybrid] Pass 1 failed (conf=%.2f). trying Pass 2 (lighter)...", ocr_conf)
        ocr_text2, ocr_conf2 = extract_with_ocr(
            pdf_path,
            bbox_200dpi=bbox_200dpi,
            page_number=page_number,
            pad_px_200dpi=float(pad_px_200dpi) + 5.0, # extra padding
            dpi=500, # higher DPI for Pass 2
            page=page,
            ocr_model=ocr_model,
            is_curved=True, # force slight blur
            orientation_hint=orientation_hint,
        )
        t2 = str(ocr_text2 or "").strip()
        if not is_dimension(t2):
            t2 = str(get_dimension_match(t2) or "").strip() # type: ignore
            
        if t2 and is_dimension(t2) and ocr_conf2 > 0.4:
            final_text = t2
            ocr_conf = ocr_conf2
            logger.debug("[hybrid] Pass 2 success: '%s' conf=%.2f", final_text, ocr_conf)

    if final_text and is_dimension(final_text):
        # STEP 7 — parse tolerance components
        parsed = parse_tolerance(final_text)
        logger.debug(
            "[hybrid] OCR hit: '%s' conf=%.2f inside box (%g,%g,%g,%g)",
            final_text, ocr_conf, x, y, w, h,
        )
        return {
            "text":   final_text,
            "method": "ocr",
            "conf":   float(ocr_conf),
            "dim":    parsed["dim"],
            "utol":   parsed["utol"],
            "ltol":   parsed["ltol"],
        }

    return _empty_result(conf=float(ocr_conf))


def _empty_result(conf: float = 0.0) -> Dict[str, Any]:
    """Return a standardised 'nothing found' result dict."""
    return {"text": "", "method": "none", "conf": conf,
            "dim": "", "utol": "0", "ltol": "0"}


# ---------------------------------------------------------------------------
# OCR internals — preprocessing
# ---------------------------------------------------------------------------

def _preprocess_for_paddle(
    img_rgb: np.ndarray,
    *,
    is_curved: bool,
    is_low_res: bool,
) -> np.ndarray:
    """
    Apply signal-boosting preprocessing before passing the crop to PaddleOCR.
    Optimized to preserve small decimal points and symbols.
    """
    if img_rgb is None or img_rgb.size == 0:
        return img_rgb

    # 1. Upscaling (3x is often safer than 4x for distortion control)
    factor = 3.0
    img = cv2.resize(
        img_rgb, (0, 0), fx=factor, fy=factor, interpolation=cv2.INTER_CUBIC
    )

    # 2. Grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)

    # 3. CLAHE (Boost contrast locally to help symbols stand out)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    gray = clahe.apply(gray)

    # 4. Conservative Sharpening (Unsharp Masking)
    # Using a larger blur kernel for safer edge enhancement
    blurred = cv2.GaussianBlur(gray, (0, 0), 2)
    gray = cv2.addWeighted(gray, 1.6, blurred, -0.6, 0)

    # 5. Conditional Blur for noisy/curved text
    if is_curved:
        gray = cv2.GaussianBlur(gray, (3, 3), 0)

    # 6. Adaptive Thresholding (increased block size to preserve dots)
    # 21px block size helps maintain connectivity in small characters
    gray = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
        cv2.THRESH_BINARY, 21, 5
    )

    # 7. Convert back to BGR for PaddleOCR
    return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
