import pymupdf
import uuid
import os

def pdf_to_jpg_service(file_path):
    doc = pymupdf.open(file_path)
    output_dir = os.path.dirname(file_path)
    output_paths = []
    for i in range(len(doc)):
        page = doc.load_page(i)
        pix = page.get_pixmap(dpi=200)
        output_path = os.path.join(output_dir, f"{uuid.uuid4().hex}_page_{i+1}.jpg")
        pix.save(output_path)
        output_paths.append(output_path)
    doc.close()
    return output_paths


def pdf_to_png_service(file_path):
    doc = pymupdf.open(file_path)
    output_dir = os.path.dirname(file_path)
    output_paths = []
    for i in range(len(doc)):
        page = doc.load_page(i)
        pix = page.get_pixmap(dpi=200)
        output_path = os.path.join(output_dir, f"{uuid.uuid4().hex}_page_{i+1}.png")
        pix.save(output_path)
        output_paths.append(output_path)
    doc.close()
    return output_paths