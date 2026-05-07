import os
import logging
from ultralytics import YOLO
import tensorflow as tf

logger = logging.getLogger(__name__)

# Global singleton model instances
_models = {}

def get_symbol_models():
    """
    Initializes and returns the symbol helper models.
    Loads YOLO (.pt) and TensorFlow (.h5) models from backend/models/
    """
    global _models
    
    if not _models:
        model_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'models')
        
        try:
            print("\n>>> [INIT] Loading Symbol Helper Models...")
            
            # 1. YOLO Models
            yolo_files = {
                'diameter': 'Diameter.pt',
                'phi': 'Phi.pt',
                'text': 'text.pt',
                'best': 'best.pt',
                'trt': 'Trt.pt',
                'trt1': 'Trt1.pt',
                'trt2': 'Trt2.pt'
            }
            
            for key, filename in yolo_files.items():
                path = os.path.join(model_dir, filename)
                if os.path.exists(path):
                    print(f"    - Loading YOLO {key}: {filename}")
                    _models[key] = YOLO(path)
                else:
                    logger.warning(f"[SymbolLoader] Model file not found: {path}")
            
            # 2. GDAN (GD&T) Model
            gdan_path = os.path.join(model_dir, 'gdan_model.h5')
            if os.path.exists(gdan_path):
                print(f"    - Loading GD&T Model: gdan_model.h5")
                _models['gdan'] = tf.keras.models.load_model(gdan_path)
            else:
                logger.warning(f"[SymbolLoader] GD&T model not found: {gdan_path}")
                
            print(">>> [SUCCESS] Symbol models loaded successfully.\n")
            
        except Exception as e:
            logger.error(f"[SymbolLoader] Error loading models: {e}")
            print(f">>> [ERROR] Failed to load symbol models: {e}")
            
    return _models

def preprocess_for_symbols(cv_img):
    """
    Standard preprocessing for symbol detection.
    Steps: Grayscale -> Sharpen -> Adaptive Threshold
    """
    import cv2
    import numpy as np
    
    if cv_img is None or cv_img.size == 0:
        return None
        
    # 1. Grayscale
    gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
    
    # 2. Sharpen
    kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
    sharpened = cv2.filter2D(gray, -1, kernel)
    
    # 3. Adaptive Threshold (for symbol clarity)
    thresh = cv2.adaptiveThreshold(
        sharpened, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
        cv2.THRESH_BINARY_INV, 11, 2
    )
    
    # 4. Slight Dilation to connect broken symbol parts
    kernel_dilate = np.ones((2,2), np.uint8)
    dilated = cv2.dilate(thresh, kernel_dilate, iterations=1)
    
    return cv2.cvtColor(dilated, cv2.COLOR_GRAY2BGR)
