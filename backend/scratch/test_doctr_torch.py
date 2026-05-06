import os
import sys
from unittest.mock import MagicMock

# Force docTR to use PyTorch
os.environ["USE_TORCH"] = "1"

# Mock weasyprint to avoid OSError on Windows
sys.modules["weasyprint"] = MagicMock()

try:
    from doctr.io import DocumentFile
    from doctr.models import ocr_predictor
    print("Successfully imported docTR with PyTorch backend and weasyprint mocked!")
except Exception as e:
    import traceback
    traceback.print_exc()
    print(f"Failed to import docTR: {e}")
