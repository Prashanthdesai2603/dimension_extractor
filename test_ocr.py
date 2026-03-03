import os
import cv2
import numpy as np
from pdf2image import convert_from_path
from doctr.models import ocr_predictor

def test_ocr():
    print("[Test] Testing PDF conversion and OCR...")
    # Find a PDF in the drawings directory
    drawings_dir = "media/drawings"
    if not os.path.exists(drawings_dir):
        print(f"[Test] Directory {drawings_dir} not found.")
        return
    
    pdfs = [f for f in os.listdir(drawings_dir) if f.lower().endswith('.pdf')]
    if not pdfs:
        print("[Test] No PDFs found to test.")
        return
    
    test_pdf = os.path.join(drawings_dir, pdfs[0])
    print(f"[Test] Testing with {test_pdf}")
    
    try:
        # Test pdf2image
        pages = convert_from_path(test_pdf, dpi=50) # Low DPI for speed
        print(f"[Test] PDF converted. Page count: {len(pages)}")
        
        # Test docTR
        predictor = ocr_predictor(pretrained=True).to("cpu")
        img = np.array(pages[0])
        res = predictor([img])
        print(f"[Test] OCR complete. Detected {len(res.pages[0].blocks)} blocks.")
        
    except Exception as e:
        print(f"[Test] FAILED: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_ocr()
