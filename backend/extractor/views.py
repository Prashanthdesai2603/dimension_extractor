"""
API Views for the extractor application.

Endpoints:
    POST /api/upload/           - Upload a PDF drawing
    POST /api/process/<id>/     - Process drawing with OCR
    GET  /api/download/<id>/    - Download extracted dimensions as .txt
"""
import logging
import os
from django.conf import settings
from django.http import HttpResponse, Http404
from django.utils import timezone
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser

from .models import UploadedDrawing

logger = logging.getLogger(__name__)
from .serializers import UploadedDrawingSerializer
from services.pipeline import process_drawing
from services.bbox_detector import detect_bounding_boxes
from services.extractor import extract_dimensions_from_bboxes
from services.tolerance_parser import format_structured_dimension


# -----------------------------------------------------------------------
# VIEW 1: Upload PDF
# -----------------------------------------------------------------------

class UploadDrawingView(APIView):
    """
    POST /api/upload/

    Accepts a multipart file upload (PDF only).
    Saves the file to media/drawings/ and creates a DB record.
    Returns the new drawing ID and basic info.
    """
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, *args, **kwargs):
        # Validate that a file was sent
        if 'file' not in request.FILES:
            return Response(
                {'error': 'No file provided. Please upload a PDF file.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        uploaded_file = request.FILES['file']

        # File type check
        if not uploaded_file.name.lower().endswith('.pdf'):
            return Response(
                {'error': 'Invalid file type. Only PDF files are accepted.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # File size check (max 50MB)
        if uploaded_file.size > 52428800:
            return Response(
                {'error': 'File too large. Maximum size is 50MB.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Create a new UploadedDrawing record
            drawing = UploadedDrawing.objects.create(file=uploaded_file)

            # Auto-detect bounding boxes immediately on upload
            pdf_path = os.path.join(settings.MEDIA_ROOT, str(drawing.file))
            try:
                suggested_bboxes = detect_bounding_boxes(pdf_path)
            except Exception as e:
                logger.warning(f"Initial detection failed for {drawing.id}: {e}")
                suggested_bboxes = []

            serializer = UploadedDrawingSerializer(
                drawing,
                context={'request': request}
            )

            return Response(
                {
                    'message': 'PDF uploaded and dimensions detected successfully.',
                    'drawing_id': drawing.id,
                    'drawing': serializer.data,
                    'suggested_bboxes': suggested_bboxes
                },
                status=status.HTTP_201_CREATED
            )

        except Exception as e:
            return Response(
                {'error': f'Upload failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# -----------------------------------------------------------------------
# VIEW 2: Process Drawing with OCR
# -----------------------------------------------------------------------

class ProcessDrawingView(APIView):
    """
    POST /api/process/<id>/

    Triggers OCR processing on an already-uploaded drawing:
    1. Finds the UploadedDrawing record by ID
    2. Runs the OCR engine pipeline on the PDF
    3. Saves the annotated image to media/processed/
    4. Saves extracted dimension text to the DB
    5. Returns image URL and list of dimensions
    """

    def post(self, request, drawing_id, *args, **kwargs):
        # Try to fetch the drawing record
        try:
            drawing = UploadedDrawing.objects.get(pk=drawing_id)
        except UploadedDrawing.DoesNotExist:
            return Response(
                {'error': f'Drawing with ID {drawing_id} not found.'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Build full path to the uploaded PDF
        pdf_path = os.path.join(settings.MEDIA_ROOT, str(drawing.file))

        if not os.path.exists(pdf_path):
            return Response(
                {'error': 'PDF file not found on server. It may have been deleted.'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Build output path for the annotated image
        # e.g. media/processed/drawing_<id>_annotated.jpg
        output_filename = f'drawing_{drawing_id}_annotated.jpg'
        output_dir = os.path.join(settings.MEDIA_ROOT, 'processed')
        output_image_path = os.path.join(output_dir, output_filename)

        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)

        # Run the refined hybrid processing pipeline
        result = process_drawing(pdf_path, output_image_path)

        if not result['success']:
            return Response(
                {
                    'error': f"Processing failed: {result['error']}",
                    'details': 'Ensure Tesseract, poppler, and PyMuPDF are installed correctly.'
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # Save results to the database
        relative_image_path = f'processed/{output_filename}'
        drawing.processed_image = relative_image_path
        drawing.extracted_text = '\n'.join(result['dimensions'])
        drawing.save()

        # Build absolute image URL for the frontend
        image_url = request.build_absolute_uri(
            f'{settings.MEDIA_URL}processed/{output_filename}'
        )

        return Response(
            {
                'message': 'Processing complete.',
                'drawing_id': drawing.id,
                'image_url': image_url,
                'dimensions': result['dimensions'],
                'dimension_count': result['valid_dimensions'],
                'total_detected': result['total_detected'],
                'valid_dimensions': result['valid_dimensions'],
                'filtered_noise': result['filtered_noise'],
                'extraction_method': result['method'],
            },
            status=status.HTTP_200_OK
        )


# -----------------------------------------------------------------------
# VIEW 3: Detect Bounding Boxes (Initial Suggestion)
# -----------------------------------------------------------------------

class DetectDrawingView(APIView):
    """
    POST /api/detect/
    Runs docTR on the PDF to suggest initial dimension rectangles.
    """
    def post(self, request, *args, **kwargs):
        drawing_id = request.data.get('drawing_id')
        if not drawing_id:
            return Response({'error': 'drawing_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            drawing = UploadedDrawing.objects.get(pk=drawing_id)
        except UploadedDrawing.DoesNotExist:
            return Response({'error': 'Drawing not found.'}, status=status.HTTP_404_NOT_FOUND)

        pdf_path = os.path.join(settings.MEDIA_ROOT, str(drawing.file))
        bboxes = detect_bounding_boxes(pdf_path)

        print(f"[Detect Response] ID: {drawing_id}, Box count: {len(bboxes)}")
        return Response({
            'drawing_id': drawing_id,
            'bboxes': bboxes
        }, status=status.HTTP_200_OK)


# -----------------------------------------------------------------------
# VIEW 4: Extract Dimensions from Adjusted Rectangles
# -----------------------------------------------------------------------

class ExtractDrawingView(APIView):
    """
    POST /api/extract/
    Frontend sends adjusted rectangles: [{x, y, width, height}]
    Backend crops regions, runs OCR, and returns structured dimensions.
    """
    def post(self, request, *args, **kwargs):
        drawing_id = request.data.get('drawing_id')
        rectangles = request.data.get('rectangles', [])

        if not drawing_id:
            return Response({'error': 'drawing_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            drawing = UploadedDrawing.objects.get(pk=drawing_id)
        except UploadedDrawing.DoesNotExist:
            return Response({'error': 'Drawing not found.'}, status=status.HTTP_404_NOT_FOUND)

        pdf_path = os.path.join(settings.MEDIA_ROOT, str(drawing.file))
        orientation = request.data.get('orientation')
        
        # Run extraction engine
        dimensions = extract_dimensions_from_bboxes(pdf_path, rectangles, orientation=orientation)

        print(f"[Extract Response] ID: {drawing_id}, Results: {dimensions}")
        return Response({
            'drawing_id': drawing_id,
            'dimensions': dimensions
        }, status=status.HTTP_200_OK)


# -----------------------------------------------------------------------
# VIEW 5: Extract from Boxes and Export .txt
# -----------------------------------------------------------------------

class ExtractFromBoxesView(APIView):
    """
    POST /api/extract_from_boxes/

    Frontend sends final box coordinates: [{x, y, width, height}, ...]
    Backend:
    - Crops regions from PDF
    - Runs docTR OCR on each region
    - Parses dimensions and tolerances
    - Generates .txt file with format: Dim: 14.9; UTol: 0.02; LTol: -0.01
    - Returns download URL
    """
    def post(self, request, *args, **kwargs):
        try:
            drawing_id = request.data.get('drawing_id')
            rectangles = request.data.get('rectangles', [])
            viewer_context = request.data.get('viewerContext')

            if not drawing_id:
                return Response({'error': 'drawing_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

            if not rectangles:
                return Response({'error': 'At least one rectangle is required.'}, status=status.HTTP_400_BAD_REQUEST)

            try:
                drawing = UploadedDrawing.objects.get(pk=drawing_id)
            except UploadedDrawing.DoesNotExist:
                return Response({'error': f'Drawing #{drawing_id} not found.'}, status=status.HTTP_404_NOT_FOUND)

            pdf_path = os.path.join(settings.MEDIA_ROOT, str(drawing.file))
            orientation = request.data.get('orientation')
            
            # Verify file exists
            if not os.path.exists(pdf_path):
                return Response({'error': f'PDF file not found on server at {pdf_path}'}, status=status.HTTP_404_NOT_FOUND)

            # Extract dimensions from the provided rectangles
            dimensions = extract_dimensions_from_bboxes(pdf_path, rectangles, viewer_context=viewer_context, orientation=orientation)

            # Filter:
            #  - Manual boxes (is_manual=True) → always keep, even if dim is empty
            #  - Auto-detected boxes → must have a real numeric dimension value
            def is_valid_dim(d):
                if d.get('is_manual'):
                    return True   # always include manual rows
                dim = str(d.get('dim', '') or '').strip()
                if not dim or dim in ('0', 'null', 'undefined', 'None'):
                    return False
                return any(c.isdigit() for c in dim)

            valid_dimensions = [d for d in dimensions if is_valid_dim(d)]

            message = f'Extracted {len(valid_dimensions)} dimensions successfully.'
            if not valid_dimensions:
                message = 'No valid numeric dimensions found in the selected regions.'

            # Generate .txt content
            # Header
            header = (
                "Engineering Drawing Dimension Extractor\n"
                "======================================\n"
                f"Drawing ID : {drawing.id}\n"
                f"File Name  : {os.path.basename(drawing.file.name)}\n"
                f"Processed  : {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"Total Dims : {len(valid_dimensions)}\n"
                "======================================\n\n"
                "EXTRACTED DIMENSIONS:\n"
                "---------------------\n"
            )

            lines = []
            for d in valid_dimensions:
                line = format_structured_dimension({
                    'dim': d['dim'],
                    'utol': d['utol'],
                    'ltol': d['ltol'],
                    'serial': d.get('serial')
                })
                lines.append(line)

            output_content = header + '\n'.join(lines)
            drawing.extracted_text = output_content
            drawing.save()

            # Build absolute download URL
            download_url = request.build_absolute_uri(f'/api/download/{drawing_id}/')

            return Response({
                'drawing_id': drawing_id,
                'message': message,
                'dimensions': valid_dimensions,
                'download_url': download_url,
                'file_content': output_content,
                'dimension_count': len(valid_dimensions)
            }, status=status.HTTP_200_OK)
        except Exception as e:
            # Catch any unexpected errors and return the message to frontend
            import traceback
            traceback.print_exc()
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# -----------------------------------------------------------------------
# VIEW 4: Export structured Dimensions
# -----------------------------------------------------------------------

class ExportDrawingView(APIView):
    """
    POST /api/export/
    Takes structured dimension data and saves it as a .txt file.
    Format: Dim: 9.0; UTol: 0.1; LTol: -0.1
    """
    def post(self, request, *args, **kwargs):
        drawing_id = request.data.get('drawing_id')
        dimensions = request.data.get('dimensions', []) # List of {dim, utol, ltol}

        if not drawing_id:
            return Response({'error': 'drawing_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            drawing = UploadedDrawing.objects.get(pk=drawing_id)
        except UploadedDrawing.DoesNotExist:
            return Response({'error': 'Drawing not found.'}, status=status.HTTP_404_NOT_FOUND)

        # Generate output text
        # Header
        header = (
            "Engineering Drawing Dimension Extractor\n"
            "======================================\n"
            f"Drawing ID : {drawing.id}\n"
            f"File Name  : {os.path.basename(drawing.file.name)}\n"
            f"Processed  : {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"Total Dims : {len(dimensions)}\n"
            "======================================\n\n"
            "EXTRACTED DIMENSIONS:\n"
            "---------------------\n"
        )

        lines = []
        for d in dimensions:
            line = format_structured_dimension(d)
            lines.append(line)
        
        output_content = header + '\n'.join(lines)
        drawing.extracted_text = output_content
        drawing.save()

        # Build absolute download URL
        download_url = request.build_absolute_uri(f'/api/download/{drawing_id}/')

        return Response({
            'drawing_id': drawing_id,
            'message': 'Dimensions exported successfully.',
            'download_url': download_url,
            'file_content': output_content
        }, status=status.HTTP_200_OK)


# -----------------------------------------------------------------------
# VIEW 3: Download Dimensions as .txt
# -----------------------------------------------------------------------

class DownloadDimensionsView(APIView):
    """
    GET /api/download/<id>/

    Downloads the extracted dimensions for a drawing as a plain text file.
    The file is named 'dimensions_<id>.txt' and returned as an attachment.
    """

    def get(self, request, drawing_id, *args, **kwargs):
        # Fetch the drawing
        try:
            drawing = UploadedDrawing.objects.get(pk=drawing_id)
        except UploadedDrawing.DoesNotExist:
            raise Http404(f'Drawing with ID {drawing_id} not found.')

        # Check that OCR has been run
        if not drawing.extracted_text:
            return Response(
                {'error': 'This drawing has not been processed yet. '
                          'Please click "Detect Dimensions" first.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Return the raw extracted text in the requested format
        content = drawing.extracted_text

        # Return as a downloadable .txt file
        response = HttpResponse(content, content_type='text/plain')
        response['Content-Disposition'] = (
            f'attachment; filename="dimensions_{drawing_id}.txt"'
        )
        return response
