"""
WSGI config for dimension_extractor project.
"""
import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dimension_extractor.settings')
application = get_wsgi_application()
