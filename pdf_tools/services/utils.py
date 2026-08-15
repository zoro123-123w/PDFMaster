import os
import uuid
from django.conf import settings


def create_output_path(extension, prefix=''):
    """Create a unique temp file path inside MEDIA_ROOT/temp for a processed output."""
    temp_dir = os.path.join(settings.MEDIA_ROOT, 'temp')
    os.makedirs(temp_dir, exist_ok=True)
    name = prefix + uuid.uuid4().hex + extension
    return os.path.join(temp_dir, name)