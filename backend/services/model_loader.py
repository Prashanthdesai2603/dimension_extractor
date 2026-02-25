from doctr.models import ocr_predictor
import torch

# Global singleton for the AI model to save VRAM/RAM
_ocr_model = None

def get_ocr_model():
    global _ocr_model
    if _ocr_model is None:
        print("[AI] Loading docTR Predictor (Pretrained)...")
        # Explicitly CPU for compatibility
        _ocr_model = ocr_predictor(pretrained=True).to("cpu")
    return _ocr_model
