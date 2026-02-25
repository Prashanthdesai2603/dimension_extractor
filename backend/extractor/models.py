"""
Database models for the extractor application.

This module defines the UploadedDrawing model which stores:
- The original uploaded PDF
- The processed/annotated image
- The extracted dimension text
"""
from django.db import models


class UploadedDrawing(models.Model):
    """
    Model representing an uploaded engineering drawing PDF.

    Fields:
        file         - The uploaded PDF file stored in media/drawings/
        uploaded_at  - Timestamp of when the file was uploaded
        processed_image - The annotated image with bounding boxes (stored in media/processed/)
        extracted_text  - The raw OCR-extracted dimension text
    """

    # Original PDF upload - stored under media/drawings/
    file = models.FileField(
        upload_to='drawings/',
        verbose_name='PDF File'
    )

    # Auto-set timestamp when drawing is first uploaded
    uploaded_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Uploaded At'
    )

    # Annotated image saved after OCR processing - stored under media/processed/
    processed_image = models.ImageField(
        upload_to='processed/',
        null=True,
        blank=True,
        verbose_name='Processed Image'
    )

    # Extracted dimensions as newline-separated text
    extracted_text = models.TextField(
        null=True,
        blank=True,
        verbose_name='Extracted Dimensions'
    )

    class Meta:
        db_table = 'uploaded_drawings'
        ordering = ['-uploaded_at']
        verbose_name = 'Uploaded Drawing'
        verbose_name_plural = 'Uploaded Drawings'

    def __str__(self):
        return f"Drawing #{self.id} - {self.file.name} ({self.uploaded_at.strftime('%Y-%m-%d %H:%M')})"
