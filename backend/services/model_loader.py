import logging
from .paddle_engine import get_paddle_ocr

logger = logging.getLogger(__name__)

def get_ocr_model():
    """
    Returns an OCR model instance. 
    Currently optimized to return the PaddleOCR singleton.
    """
    try:
        return get_paddle_ocr()
    except Exception as e:
        logger.error(f"[Model Loader] Failed to load OCR model: {e}")
        return None

# For backward compatibility with scripts expecting a 'doctr' style caller
class DoctrWrapper:
    def __init__(self):
        self.ocr = get_paddle_ocr()
    
    def __call__(self, images):
        # docTR expects list of images, returns Document
        # Here we just return the raw Paddle results for now or a mock
        # For full compatibility, more mapping would be needed.
        return self.ocr.ocr(images[0])
