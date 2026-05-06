"""
Django Admin configuration for the extractor application.
"""
from django.contrib import admin
from .models import UploadedDrawing


@admin.register(UploadedDrawing)
class UploadedDrawingAdmin(admin.ModelAdmin):
    """Admin panel configuration for viewing uploaded drawings."""
    list_display = ['id', 'file', 'uploaded_at', 'has_processed_image', 'dimension_count']
    list_filter = ['uploaded_at']
    readonly_fields = ['uploaded_at', 'processed_image', 'extracted_text']
    search_fields = ['file']
    ordering = ['-uploaded_at']

    def has_processed_image(self, obj):
        """Show a checkmark if the drawing has been processed."""
        return bool(obj.processed_image)
    has_processed_image.boolean = True
    has_processed_image.short_description = 'Processed?'

    def dimension_count(self, obj):
        """Show count of extracted dimensions."""
        if obj.extracted_text:
            return len([d for d in obj.extracted_text.splitlines() if d.strip()])
        return 0
    dimension_count.short_description = 'Dimensions Found'
