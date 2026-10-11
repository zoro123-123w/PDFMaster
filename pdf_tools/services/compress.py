"""Compress a PDF.

Three quality levels are offered to the user:

* ``low``     - structural only: dedupe objects and compact, images untouched.
               Fast, fully lossless for content.
* ``medium``  - also recompress embedded images as JPEG (q~70). Much smaller,
               only tiny visible loss.
* ``high``    - recompress images harder (q~45), downscale, and strip metadata.
               Smallest file, more visible loss.

The pypdf structural pass always runs; the image pass uses PyMuPDF's
``rewrite_images`` which re-encodes image XObjects in place without rasterising
text. If the image pass fails or is not available, we fall back to the
structural result (and always keep whichever file is actually smaller).
"""
import inspect
import os
import uuid

import pymupdf
from pypdf import PdfReader, PdfWriter

# quality -> preset dict.
QUALITY_PRESETS = {
    'low': dict(images=False, jpeg=95, scale=1.0, strip=False),
    'medium': dict(images=True, jpeg=70, scale=1.0, strip=False),
    'high': dict(images=True, jpeg=45, scale=0.75, strip=True),
}


def _structural_compress(file_path, output_path):
    """pypdf pass: dedupe objects and compact the file (always lossless)."""
    reader = PdfReader(file_path)
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    writer.compress_identical_objects()
    with open(output_path, 'wb') as f:
        writer.write(f)


def _image_compress(input_path, output_path, preset):
    """PyMuPDF pass: recompress embedded images per the preset."""
    doc = pymupdf.open(input_path)
    if preset['strip']:
        doc.set_metadata({})
    # rewrite_images recompresses images above dpi_threshold down to dpi_target;
    # PyMuPDF requires dpi_target < dpi_threshold. A smaller preset scale means
    # catch more images (lower threshold) and downscale them harder (lower
    # target). Signature varies by PyMuPDF version, so pass only known kwargs.
    threshold = max(int(150 * preset['scale']), 50)
    kwargs = dict(
        dpi_threshold=threshold,
        dpi_target=max(int(threshold * 0.75), 36),
        quality=preset['jpeg'],
        lossy=True,
        lossless=False,
    )
    params = inspect.signature(doc.rewrite_images).parameters
    if 'set_soft_mask' in params:
        kwargs['set_soft_mask'] = True
    doc.rewrite_images(**kwargs)
    doc.save(output_path, garbage=4, deflate=True, clean=True)
    doc.close()


def compress_pdf_service(file_path, quality='low'):
    """Return the path to a compressed copy of ``file_path``.

    ``quality`` is one of ``low`` / ``medium`` / ``high`` (unknown values fall
    back to ``low``).
    """
    if quality not in QUALITY_PRESETS:
        quality = 'low'
    preset = QUALITY_PRESETS[quality]
    out_dir = os.path.dirname(file_path)
    structural_path = os.path.join(out_dir, uuid.uuid4().hex + '.pdf')
    _structural_compress(file_path, structural_path)

    if not preset['images']:
        return structural_path

    final_path = os.path.join(out_dir, uuid.uuid4().hex + '.pdf')
    try:
        _image_compress(structural_path, final_path, preset)
        # Keep whichever result is actually smaller.
        if os.path.getsize(final_path) < os.path.getsize(structural_path):
            os.remove(structural_path)
            return final_path
        os.remove(final_path)
        return structural_path
    except Exception:
        # Any failure in the image pass: the structural result is still valid.
        try:
            os.remove(final_path)
        except OSError:
            pass
        return structural_path
