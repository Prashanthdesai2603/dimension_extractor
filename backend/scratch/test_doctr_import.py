import sys
from unittest.mock import MagicMock

# Mock weasyprint to avoid OSError on Windows when importing doctr
sys.modules["weasyprint"] = MagicMock()

try:
    from doctr.io import DocumentFile
    print("Successfully imported DocumentFile with weasyprint mocked!")
except Exception as e:
    print(f"Failed to import DocumentFile: {e}")
