from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
import uuid
import os

def jpg_to_pdf_service(file_paths):
    output_path = os.path.join(os.path.dirname(file_paths[0]), f"{uuid.uuid4().hex}.pdf")
    c = canvas.Canvas(output_path, pagesize=letter)
    for img_path in file_paths:
        img = Image.open(img_path)
        width, height = img.size
        aspect = height / float(width)
        page_width, page_height = letter
        if width > height:
            new_width = page_width
            new_height = page_width * aspect
        else:
            new_height = page_height
            new_width = page_height / aspect
        if new_width > page_width:
            new_width = page_width
            new_height = page_width * aspect
        if new_height > page_height:
            new_height = page_height
            new_width = page_height / aspect
        c.setPageSize((page_width, page_height))
        c.drawImage(img_path, (page_width - new_width) / 2, (page_height - new_height) / 2, width=new_width, height=new_height)
        c.showPage()
    c.save()
    return output_path