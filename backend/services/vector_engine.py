import fitz  # PyMuPDF
import re

def extract_vector_text(pdf_path: str, dpi: int = 200):
    """
    Extracts text blocks with their coordinates from a vector PDF.
    Scales coordinates from 72 DPI (points) to requested DPI (usually 200).
    """
    doc = fitz.open(pdf_path)
    all_tokens = []
    scale = dpi / 72.0
    
    # Process only the first page for now
    if len(doc) > 0:
        page = doc[0]
        # get_text("dict") returns detailed information including coordinates
        text_dict = page.get_text("dict")
        
        for block in text_dict.get("blocks", []):
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = span["text"].strip()
                    if text:
                        # Scale raw points to target DPI
                        x0, y0, x1, y1 = span["bbox"]
                        
                        all_tokens.append({
                            "text": text,
                            "bbox": (x0 * scale, y0 * scale, x1 * scale, y1 * scale),
                            "font": span["font"],
                            "size": span["size"]
                        })
    
    doc.close()
    
    print(f"[Vector Engine] Total text blocks detected: {len(all_tokens)}")
    return all_tokens

def has_vector_text(pdf_path: str):
    """
    Checks if the PDF has a text layer.
    """
    doc = fitz.open(pdf_path)
    has_text = False
    if len(doc) > 0:
        page = doc[0]
        text = page.get_text().strip()
        if text:
            # Check if text length is reasonable for a vector layer
            has_text = len(text) > 0
    doc.close()
    return has_text
