"""E-signature service.

Places a user-drawn/typed signature image onto a chosen page of a PDF using
PyMuPDF. The signature image is temporary and deleted after the signed PDF
is produced.
"""
import base64
import binascii
import os
import tempfile

from .utils import create_output_path


class SignatureError(Exception):
    pass


def decode_signature_image(b64_data):
    """Decode a data-URL/base64 PNG or JPEG into raw bytes."""
    if not b64_data:
        raise SignatureError('No signature provided.')
    data = b64_data
    if data.startswith('data:'):
        # strip "data:image/png;base64,"
        data = data.split(',', 1)[-1]
    try:
        raw = base64.b64decode(data)
    except (binascii.Error, ValueError):
        raise SignatureError('Signature image data is invalid.')
    if not raw:
        raise SignatureError('Signature image is empty.')
    # Sanity check it looks like a PNG or JPEG.
    if not (raw.startswith(b'\x89PNG') or raw[:3] in (b'\xff\xd8\xff',)):
        raise SignatureError('Unsupported signature image format (PNG or JPEG expected).')
    return raw


def sign_pdf(file_path, signature_bytes, page_no=1, x_pct=50, y_pct=50,
             width_pct=25):
    """Place the signature image on page `page_no`.

    x_pct / y_pct are percentage positions from the top-left of the page.
    width_pct is the signature width as a percentage of page width.
    """
    if x_pct is None:
        x_pct = 50
    try:
        x_pct = float(x_pct)
        y_pct = float(y_pct)
        width_pct = float(width_pct)
    except (TypeError, ValueError):
        x_pct, y_pct, width_pct = 50.0, 50.0, 25.0
    width_pct = max(10.0, min(50.0, width_pct))

    import fitz

    output_path = create_output_path('.pdf', 'signed_')
    pdf = fitz.open(file_path)
    try:
        total = len(pdf)
        if total == 0:
            raise SignatureError('The PDF contains no pages.')
        try:
            index = int(page_no) - 1
        except (TypeError, ValueError):
            index = 0
        index = max(0, min(index, total - 1))
        page = pdf[index]

        tmp = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
        temp_path = tmp.name
        try:
            tmp.write(signature_bytes)
            tmp.close()
            page_width = page.rect.width
            sig_width = page_width * (width_pct / 100.0)
            aspect = page.rect.height / page_width
            sig_height = sig_width * 0.35  # signatures are wide, not high
            x = page_width * (x_pct / 100.0)
            y = page.rect.height * (y_pct / 100.0)
            place = fitz.Rect(x, y, x + sig_width, y + sig_height)
            place = place & page.rect  # keep within the page
            page.insert_image(place, filename=temp_path)
        finally:
            tmp.close()
            try:
                os.remove(temp_path)
            except OSError:
                pass
        pdf.save(output_path, garbage=3, deflate=True)
    finally:
        pdf.close()
    return output_path, total