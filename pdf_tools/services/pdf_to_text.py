"""Extract the embedded text layer from a PDF as a plain .txt file.

This is *not* OCR - it reads text that already exists in the PDF (born-digital
documents). For scanned/image-only PDFs, use the OCR tool instead, which will
build a text layer first.
"""
import os
import uuid

import pymupdf
from django.conf import settings


def pdf_to_text_service(file_path):
    """Return the path to a new .txt file containing the PDF's text."""
    doc = pymupdf.open(file_path)
    parts = []
    for page in doc:
        parts.append(page.get_text())
    doc.close()
    text = '\n\n'.join(part.rstrip() for part in parts)
    if not text.strip():
        raise ValueError(
            'No text layer found in this PDF. If it is a scan, use the OCR tool '
            'instead - it reads the image and adds searchable text.')
    out_path = os.path.join(settings.MEDIA_ROOT, 'temp',
                            uuid.uuid4().hex + '.txt')
    with open(out_path, 'w', encoding='utf-8') as fh:
        fh.write(text)
    return out_path
