from pypdf import PdfReader, PdfWriter
import uuid
import os

def compress_pdf_service(file_path):
    reader = PdfReader(file_path)
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    writer.compress_identical_objects()
    output_path = os.path.join(os.path.dirname(file_path), f"{uuid.uuid4().hex}.pdf")
    with open(output_path, 'wb') as f:
        writer.write(f)
    return output_path