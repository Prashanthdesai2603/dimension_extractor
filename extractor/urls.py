"""
URL routing for the extractor application.

All URLs are prefixed with /api/ from the root URL configuration.
"""
from django.urls import path
from .views import (
    UploadDrawingView, 
    ProcessDrawingView, 
    DownloadDimensionsView,
    DetectDrawingView,
    ExtractDrawingView,
    ExportDrawingView
)

app_name = 'extractor'

urlpatterns = [
    # POST /api/upload/ - Upload a PDF drawing
    path('upload/', UploadDrawingView.as_view(), name='upload-drawing'),

    # POST /api/process/<id>/ - Run OCR (Legacy/Auto)
    path('process/<int:drawing_id>/', ProcessDrawingView.as_view(), name='process-drawing'),

    # POST /api/detect/ - Get AI suggested bboxes
    path('detect/', DetectDrawingView.as_view(), name='detect-drawing'),

    # POST /api/extract/ - Extract dimensions from provided bboxes
    path('extract/', ExtractDrawingView.as_view(), name='extract-drawing'),

    # POST /api/export/ - Save structured data and get download link
    path('export/', ExportDrawingView.as_view(), name='export-drawing'),

    # GET /api/download/<id>/ - Download extracted dimensions as .txt
    path('download/<int:drawing_id>/', DownloadDimensionsView.as_view(), name='download-dimensions'),
]
