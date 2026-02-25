"""
App configuration for the extractor Django application.
"""
from django.apps import AppConfig


class ExtractorConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'extractor'
    verbose_name = 'Dimension Extractor'
