from pypdf import PdfReader, PdfWriter
import uuid
import os

def rotate_pdf_service(file_path, angle):
    reader = PdfReader(file_path)
    writer = PdfWriter()
    for page in reader.pages:
        page.rotate(angle)
        writer.add_page(page)
    output_path = os.path.join(os.path.dirname(file_path), f"{uuid.uuid4().hex}.pdf")
    with open(output_path, 'wb') as f:
        writer.write(f)
    return output_path