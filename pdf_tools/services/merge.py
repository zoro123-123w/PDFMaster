from pypdf import PdfWriter, PdfReader
import uuid
import os

def merge_pdf_service(file_paths):
    writer = PdfWriter()
    for path in file_paths:
        reader = PdfReader(path)
        for page in reader.pages:
            writer.add_page(page)
    output_path = os.path.join(os.path.dirname(file_paths[0]), f"{uuid.uuid4().hex}.pdf")
    with open(output_path, 'wb') as f:
        writer.write(f)
    return output_path