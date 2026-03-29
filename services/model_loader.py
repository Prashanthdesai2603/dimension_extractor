import sys
# Compatibility patch for newer langchain versions that PaddleOCR might expect
try:
    import langchain_community.docstore as docstore
    sys.modules['langchain.docstore'] = docstore
    import langchain_text_splitters as text_splitter
    sys.modules['langchain.text_splitter'] = text_splitter
except ImportError:
    pass

from paddleocr import PaddleOCR
import torch

# Global singleton for the AI models to save VRAM/RAM
_paddle_ocr = None

def get_paddle_ocr():
    """
    Returns a singleton instance of PaddleOCR.
    """
    global _paddle_ocr
    if _paddle_ocr is None:
        print("[AI] Loading PaddleOCR (En)...")
        # cls=True enables the orientation classifier (good for 90/270 deg text)
        _paddle_ocr = PaddleOCR(use_angle_cls=True, lang='en')
    return _paddle_ocr

def get_ocr_model():
    """
    Legacy helper for transitioning away from docTR.
    Returns the paddle model instead.
    """
    return get_paddle_ocr()
