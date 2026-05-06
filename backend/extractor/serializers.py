"""
Serializers for the extractor application.

Converts Django model instances to/from JSON for the REST API.
"""
from rest_framework import serializers
from .models import UploadedDrawing


class UploadedDrawingSerializer(serializers.ModelSerializer):
    """
    Serializer for the UploadedDrawing model.
    Exposes all relevant fields via the REST API.
    """

    # Include full URL for file fields instead of just relative paths
    file_url = serializers.SerializerMethodField()
    processed_image_url = serializers.SerializerMethodField()

    class Meta:
        model = UploadedDrawing
        fields = [
            'id',
            'file',
            'file_url',
            'uploaded_at',
            'processed_image',
            'processed_image_url',
            'extracted_text',
        ]
        read_only_fields = ['id', 'uploaded_at', 'processed_image', 'extracted_text']

    def get_file_url(self, obj):
        """Return the absolute URL for the uploaded PDF file."""
        request = self.context.get('request')
        if obj.file and request:
            return request.build_absolute_uri(obj.file.url)
        return None

    def get_processed_image_url(self, obj):
        """Return the absolute URL for the processed/annotated image."""
        request = self.context.get('request')
        if obj.processed_image and request:
            return request.build_absolute_uri(obj.processed_image.url)
        return None


class UploadSerializer(serializers.Serializer):
    """
    Serializer used specifically for the file upload endpoint.
    Only accepts a PDF file upload.
    """
    file = serializers.FileField()

    def validate_file(self, value):
        """Validate that the uploaded file is a PDF."""
        if not value.name.lower().endswith('.pdf'):
            raise serializers.ValidationError("Only PDF files are accepted.")
        return value
