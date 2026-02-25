import os
import cv2
import numpy as np
import torch
from doctr.io import DocumentFile
from .model_loader import get_ocr_model

def run_doctr_ocr(pdf_path: str, img_width: int, img_height: int) -> list:
    """
    Run docTR OCR on a PDF and return formatted word-level data.
    
    Args:
        pdf_path: Path to the PDF file.
        img_width: Width of the image the results will be mapped to.
        img_height: Height of the image the results will be mapped to.
        
    Returns:
        list: A list of dicts with 'text' and 'bbox' (x0, y0, x1, y1).
    """
    # Load PDF
    doc = DocumentFile.from_pdf(pdf_path)
    
    ocr_model = get_ocr_model()
    # Analyze the PDF (Processing only the first page for the current scope)
    result = ocr_model(doc[:1])
    
    tokens = []
    
    # Process output
    for page in result.pages:
        for block in page.blocks:
            for line in block.lines:
                for word in line.words:
                    text = word.value.strip()
                    if text:
                        # docTR returns relative coordinates (0 to 1) 
                        # in the format [[x_min, y_min], [x_max, y_max]]
                        geometry = word.geometry
                        (x_min, y_min), (x_max, y_max) = geometry
                        
                        # Convert to absolute pixels
                        x0 = x_min * img_width
                        y0 = y_min * img_height
                        x1 = x_max * img_width
                        y1 = y_max * img_height
                        
                        tokens.append({
                            'text': text,
                            'bbox': (x0, y0, x1, y1),
                            'conf': word.confidence
                        })
    
    return tokens
