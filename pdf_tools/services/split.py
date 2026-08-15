from pypdf import PdfReader, PdfWriter
import uuid
import os

def parse_ranges(ranges_str, total_pages):
    pages = set()
    parts = ranges_str.replace(' ', '').split(',')
    for part in parts:
        if '-' in part:
            start, end = part.split('-')
            start = int(start)
            end = int(end)
            if start < 1 or end > total_pages or start > end:
                raise ValueError(f"Invalid range: {part}")
            pages.update(range(start - 1, end))
        else:
            p = int(part)
            if p < 1 or p > total_pages:
                raise ValueError(f"Invalid page number: {part}")
            pages.add(p - 1)
    return sorted(pages)

def split_pdf_service(file_path, ranges_str):
    reader = PdfReader(file_path)
    total_pages = len(reader.pages)
    pages = parse_ranges(ranges_str, total_pages)
    if not pages:
        raise ValueError("No valid pages selected")
    writer = PdfWriter()
    for p in pages:
        writer.add_page(reader.pages[p])
    output_path = os.path.join(os.path.dirname(file_path), f"{uuid.uuid4().hex}.pdf")
    with open(output_path, 'wb') as f:
        writer.write(f)
    return output_path