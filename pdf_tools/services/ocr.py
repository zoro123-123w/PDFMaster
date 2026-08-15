"""OCR service.

Uses Tesseract (via pytesseract) on page images rendered by PyMuPDF, so no
Poppler is required. On Windows the default install path is detected; the
path can also be supplied through settings.TESSERACT_CMD (from the
TESSERACT_CMD environment variable) — this keeps Render deployments working
when tesseract is on PATH.
"""
import io
import os
import sys
from django.conf import settings

from .utils import create_output_path


class OCRNotConfiguredError(Exception):
    """Raised when the Tesseract binary is not available."""


def _resolve_tesseract_cmd():
    configured = getattr(settings, 'TESSERACT_CMD', '') or ''
    if configured and os.path.exists(configured):
        return configured
    windows_default = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
    if sys.platform.startswith('win') and os.path.exists(windows_default):
        return windows_default
    return 'tesseract'


def tesseract_available():
    """Return True if a usable Tesseract binary is present."""
    import shutil
    cmd = _resolve_tesseract_cmd()
    if not cmd:
        return False
    if os.path.exists(cmd):
        return True
    return shutil.which(cmd) is not None


def ocr_pdf(file_path, data=None):
    """Render each specified page to an image, run OCR, and write results back
    as a searchable text layer into a new PDF."""
    import pytesseract

    if not tesseract_available():
        raise OCRNotConfiguredError(
            'OCR is not configured on this server. Install Tesseract '
            '(apt-get install tesseract-ocr) and set TESSERACT_CMD if needed.')

    import fitz
    from .edit import parse_page_list

    pages_str = (data or {}).get('pages') or ''
    lang = (data or {}).get('lang') or getattr(settings, 'OCR_LANG', 'eng')
    dpi = int((data or {}).get('dpi') or 200)

    output_path = create_output_path('.pdf', 'ocr_')
    pdf = fitz.open(file_path)
    try:
        total = len(pdf)
        wanted = set()
        if pages_str.strip():
            wanted = set(parse_page_list(pages_str, total))
        for i, page in enumerate(pdf):
            if wanted and (i + 1) not in wanted:
                continue
            try:
                pix = page.get_pixmap(dpi=dpi)
                img_bytes = pix.tobytes('png')
                from PIL import Image
                image = Image.open(io.BytesIO(img_bytes))
                text = pytesseract.image_to_string(image, lang=lang)
            except pytesseract.TesseractNotFoundError:
                raise OCRNotConfiguredError(
                    'Tesseract executable was not found on this server.')
            except OCRNotConfiguredError:
                raise
            except Exception as exc:
                # Never expose raw OCR stack traces to the user.
                raise ValueError(f'OCR failed on page {i + 1}: {type(exc).__name__}')
            if text and text.strip():
                # Invisible text layer => searchable PDF.
                page.insert_textbox(page.rect, text, fontsize=10,
                                    fontname='helv', render_mode=3)
        pdf.save(output_path, garbage=3, deflate=True)
    finally:
        pdf.close()
    return output_path