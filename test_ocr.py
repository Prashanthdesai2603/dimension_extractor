import os
import cv2
import numpy as np
from pdf2image import convert_from_path
from paddleocr import PaddleOCR

def test_ocr():
    print("[Test] Testing PDF conversion and PaddleOCR...")
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
        pages = convert_from_path(test_pdf, dpi=200)
        print(f"[Test] PDF converted. Page count: {len(pages)}")
        
        # Test PaddleOCR
        ocr = PaddleOCR(use_angle_cls=True, lang='en')
        img = cv2.cvtColor(np.array(pages[0]), cv2.COLOR_RGB2BGR)
        res = ocr.ocr(img, cls=True)
        
        print(f"[Test] OCR complete. Detected {len(res[0]) if res and res[0] else 0} fragments.")
        if res and res[0]:
            print(f"[Test] Sample text: {res[0][0][1][0]}")
        
    except Exception as e:
        print(f"[Test] FAILED: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_ocr()
