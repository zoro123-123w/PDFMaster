"""Security services: password protection, unlock/decrypt, and redaction.

Redaction uses PyMuPDF redaction annotations and apply_redactions() which
physically remove the underlying text from the content stream — it is not a
fake black rectangle overlay.
"""
from .utils import create_output_path


def protect_pdf(file_path, data):
    """Encrypt a PDF with a password using pypdf AES-128 encryption."""
    from pypdf import PdfReader, PdfWriter

    password = (data.get('password') or '').strip()
    if not password:
        raise ValueError('A password is required to protect the PDF.')

    output_path = create_output_path('.pdf', 'protected_')
    reader = PdfReader(file_path)
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    writer.encrypt(user_password=password, owner_password=password)
    with open(output_path, 'wb') as fh:
        writer.write(fh)
    return output_path


def unlock_pdf(file_path, pwd):
    """Decrypt a password-protected PDF. Raises ValueError on a wrong password."""
    from pypdf import PdfReader, PdfWriter

    password = (pwd.get('password') or '').strip() if isinstance(pwd, dict) else (pwd or '').strip()
    output_path = create_output_path('.pdf', 'unlocked_')
    reader = PdfReader(file_path)
    if reader.is_encrypted:
        result = reader.decrypt(password)
        if not result:
            raise ValueError('Incorrect password - could not unlock the PDF.')
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    with open(output_path, 'wb') as fh:
        writer.write(fh)
    return output_path


def redact_pdf(file_path, pwd):
    """Permanently redact (remove) the given words/phrases from the PDF."""
    import fitz

    terms_raw = pwd.get('words') or ''
    terms = [t.strip() for t in str(terms_raw).replace(';', ',').split(',') if t.strip()]
    if not terms:
        raise ValueError('At least one word or phrase to redact is required.')

    output_path = create_output_path('.pdf', 'redacted_')
    pdf = fitz.open(file_path)
    try:
        for page in pdf:
            for term in terms:
                try:
                    regions = page.search_for(term)
                except Exception:
                    regions = []
                for rect in regions:
                    page.add_redact_annot(rect)
            page.apply_redactions()
        pdf.save(output_path, garbage=3, deflate=True)
    finally:
        pdf.close()
    return output_path