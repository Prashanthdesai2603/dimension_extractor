import sys
# Compatibility patch for newer langchain versions that PaddleOCR might expect
try:
    import langchain_community.docstore as docstore
    sys.modules['langchain.docstore'] = docstore
    import langchain_text_splitters as text_splitter
    sys.modules['langchain.text_splitter'] = text_splitter
except ImportError:
    pass
