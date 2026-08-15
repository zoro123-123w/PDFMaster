"""PDF editing services: crop, watermark, page numbers, reorganize, and repair.

Crop uses PyMuPDF's set_cropbox (the crop is honoured in the saved output).
Watermark / page numbers use PyMuPDF text rendering with opacity support.
Organize reorders and rotates pages using pypdf.
Repair re-saves through PyMuPDF with aggressive garbage collection.
"""
from .utils import create_output_path


def crop_pdf(file_path, data):
    """Crop pages. Values left/right/top/bottom are percentages cropped off
    each edge (0-100). Optional 'pages' uses 1-based ranges e.g. '1-3,5'."""
    import fitz

    def _pct(value, default=0):
        try:
            v = float(value)
        except (TypeError, ValueError):
            return default
        return max(0.0, min(100.0, v))

    left = _pct(data.get('left'), 0)
    right = _pct(data.get('right'), 0)
    top = _pct(data.get('top'), 0)
    bottom = _pct(data.get('bottom'), 0)
    if left + right >= 100 or top + bottom >= 100:
        raise ValueError('Crop margins are too large (combined value must stay under 100%).')

    output_path = create_output_path('.pdf', 'cropped_')
    pdf = fitz.open(file_path)
    try:
        total = len(pdf)
        wanted = set()
        if data.get('pages'):
            wanted = set(parse_page_list(data['pages'], total))
        for i, page in enumerate(pdf):
            if wanted and (i + 1) not in wanted:
                continue
            rect = page.rect
            x0 = rect.width * (left / 100.0)
            x1 = rect.width * (1 - right / 100.0)
            y0 = rect.height * (top / 100.0)
            y1 = rect.height * (1 - bottom / 100.0)
            if x1 - x0 < 10 or y1 - y0 < 10:
                raise ValueError('Resulting crop box is too small for the page.')
            page.set_cropbox(fitz.Rect(x0, y0, x1, y1))
        pdf.save(output_path, garbage=3, deflate=True)
    finally:
        pdf.close()
    return output_path


def watermark_pdf(file_path, data):
    """Add a semi-transparent text watermark to every page (or selected pages)."""
    import fitz

    text = (data.get('text') or '').strip()
    if not text:
        raise ValueError('Watermark text is required.')
    position = data.get('position') or 'center'
    opacity = float(data.get('opacity') or 0.3)
    opacity = max(0.05, min(1.0, opacity))
    fontsize = float(data.get('fontsize') or 30)

    output_path = create_output_path('.pdf', 'watermarked_')
    pdf = fitz.open(file_path)
    try:
        total = len(pdf)
        wanted = set()
        if data.get('pages'):
            wanted = set(parse_page_list(data['pages'], total))
        for i, page in enumerate(pdf):
            if wanted and (i + 1) not in wanted:
                continue
            rect = page.rect
            text_width = fitz.get_text_length(text, fontname='helv', fontsize=fontsize)
            text_height = fontsize * 1.2
            w, h = rect.width, rect.height
            positions = {
                'center': ((w - text_width) / 2, (h - text_height) / 2),
                'top-left': (20, 20),
                'top-center': ((w - text_width) / 2, 20),
                'top-right': (w - text_width - 20, 20),
                'bottom-left': (20, h - text_height - 20),
                'bottom-center': ((w - text_width) / 2, h - text_height - 20),
                'bottom-right': (w - text_width - 20, h - text_height - 20),
            }
            x, y = positions.get(position, positions['center'])
            box = fitz.Rect(max(0, x), max(0, y),
                            min(w, x + text_width + 4),
                            min(h, y + text_height + 4))
            page.insert_textbox(
                box, text, fontsize=fontsize, fontname='helv',
                color=(0.35, 0.35, 0.45),
                fill_opacity=opacity, stroke_opacity=opacity,
                align=fitz.TEXT_ALIGN_CENTER,
            )
        pdf.save(output_path, garbage=3, deflate=True)
    finally:
        pdf.close()
    return output_path


def add_page_numbers(file_path, data):
    """Add page numbers at a chosen position starting from 'start'."""
    import fitz

    position = data.get('position') or 'bottom-center'
    try:
        start = int(data.get('start') or 1)
    except (TypeError, ValueError):
        start = 1
    fontsize = float(data.get('fontsize') or 14)

    output_path = create_output_path('.pdf', 'numbered_')
    pdf = fitz.open(file_path)
    try:
        for i, page in enumerate(pdf):
            number = start + i
            label = str(number)
            text_width = fitz.get_text_length(label, fontname='helv', fontsize=fontsize)
            rect = page.rect
            w, h = rect.width, rect.height
            positions = {
                'top-left': (20, 20),
                'top-center': ((w - text_width) / 2, 20),
                'top-right': (w - text_width - 20, 20),
                'bottom-left': (20, h - 20),
                'bottom-center': ((w - text_width) / 2, h - 20),
                'bottom-right': (w - text_width - 20, h - 20),
            }
            x, y = positions.get(position, positions['bottom-center'])
            page.insert_text((x, y), label, fontsize=fontsize,
                             fontname='helv', color=(0, 0, 0))
        pdf.save(output_path, garbage=3, deflate=True)
    finally:
        pdf.close()
    return output_path


def organize_pdf(file_path, data):
    """Reorder PDF pages using order syntax like '1,3,2' or '2-4,1' and apply
    an optional rotation (90/180/270)."""
    from pypdf import PdfReader, PdfWriter

    order_str = (data.get('order') or '').strip()
    if not order_str:
        raise ValueError('Please provide a new page order.')
    rotation = int(data.get('rotation') or 0)
    if rotation not in (0, 90, 180, 270):
        rotation = 0

    reader = PdfReader(file_path)
    total = len(reader.pages)
    indices = parse_order(order_str, total)

    output_path = create_output_path('.pdf', 'organized_')
    writer = PdfWriter()
    seen = set()
    for idx in indices:
        if idx in seen:
            continue
        seen.add(idx)
        page = reader.pages[idx - 1]  # parse_order is 1-based
        if rotation:
            page.rotate(rotation)
        writer.add_page(page)
    with open(output_path, 'wb') as fh:
        writer.write(fh)
    return output_path


def repair_pdf(file_path, data=None):
    """Attempt to repair a PDF by re-writing it through PyMuPDF."""
    import fitz

    output_path = create_output_path('.pdf', 'repaired_')
    pdf = fitz.open(file_path)
    try:
        pdf.save(output_path, garbage=4, deflate=True, clean=True)
    finally:
        pdf.close()
    return output_path


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def parse_page_list(value, total):
    """Expand '1-3,5' style ranges into 1-based integer list (clamped)."""
    from .split import parse_ranges as _pr
    return [i for i in _pr(str(value), total) if 1 <= i <= total]


def parse_order(order_str, total):
    """Expand an order string such as '2,1' or '1-3,5,4' into a 1-based list."""
    import re
    result = []
    for token in order_str.split(','):
        token = token.strip()
        if not token:
            continue
        m = re.match(r'^(\d+)\s*-\s*(\d+)$', token)
        if m:
            first, last = int(m.group(1)), int(m.group(2))
            if first < 1 or last < 1 or first > total or last > total:
                raise ValueError(f'Page range "{token}" is outside the document.')
            step = 1 if last >= first else -1
            result.extend(range(first, last + step, step))
        elif token.isdigit():
            n = int(token)
            if n < 1 or n > total:
                raise ValueError(f'Page "{token}" does not exist in the document.')
            result.append(n)
        else:
            raise ValueError(f'Invalid order syntax near "{token}".')
    if not result:
        raise ValueError('Ordered result is empty - please check your input.')
    return result


# ---------------------------------------------------------------------------
# Add text to PDF
# ---------------------------------------------------------------------------

def add_text_to_pdf(file_path, data):
    """Add a text string onto a specific page at a percentage position."""
    import fitz

    text = (data.get('text') or '').strip()
    if not text:
        raise ValueError('Text to add is required.')
    try:
        page_number = int(data.get('page_number') or 1)
    except (TypeError, ValueError):
        page_number = 1
    try:
        x_pct = float(data.get('x') or 50)
        y_pct = float(data.get('y') or 50)
        fontsize = float(data.get('fontsize') or 12)
    except (TypeError, ValueError):
        x_pct, y_pct, fontsize = 50.0, 50.0, 12.0
    x_pct = max(0, min(100, x_pct))
    y_pct = max(0, min(100, y_pct))
    fontsize = max(6, min(72, fontsize))

    output_path = create_output_path('.pdf', 'text_added_')
    pdf = fitz.open(file_path)
    try:
        total = len(pdf)
        if page_number < 1 or page_number > total:
            raise ValueError(f'Page {page_number} does not exist (document has {total} pages).')
        page = pdf[page_number - 1]
        rect = page.rect
        x = rect.width * (x_pct / 100.0)
        y = rect.height * (y_pct / 100.0)
        page.insert_text((x, y), text, fontsize=fontsize,
                         fontname='helv', color=(0, 0, 0))
        pdf.save(output_path, garbage=3, deflate=True)
    finally:
        pdf.close()
    return output_path


# ---------------------------------------------------------------------------
# Add image to PDF
# ---------------------------------------------------------------------------

def add_image_to_pdf(file_path, image_path, data):
    """Place an image onto a specific page at percentage positions."""
    import fitz

    try:
        page_number = int(data.get('page_number') or 1)
    except (TypeError, ValueError):
        page_number = 1
    try:
        x_pct = float(data.get('x') or 50)
        y_pct = float(data.get('y') or 50)
        width_pct = float(data.get('width_pct') or 25)
    except (TypeError, ValueError):
        x_pct, y_pct, width_pct = 50.0, 50.0, 25.0
    width_pct = max(5, min(80, width_pct))

    output_path = create_output_path('.pdf', 'image_added_')
    pdf = fitz.open(file_path)
    try:
        total = len(pdf)
        if page_number < 1 or page_number > total:
            raise ValueError(f'Page {page_number} does not exist (document has {total} pages).')
        page = pdf[page_number - 1]
        rect = page.rect
        sig_width = rect.width * (width_pct / 100.0)
        x = rect.width * (x_pct / 100.0)
        y = rect.height * (y_pct / 100.0)
        place = fitz.Rect(x, y, x + sig_width, y + sig_width)
        place = place & page.rect
        page.insert_image(place, filename=image_path)
        pdf.save(output_path, garbage=3, deflate=True)
    finally:
        pdf.close()
    return output_path


# ---------------------------------------------------------------------------
# Annotate PDF
# ---------------------------------------------------------------------------

def annotate_pdf(file_path, data):
    """Add a text annotation box onto a specific page."""
    import fitz

    text = (data.get('text') or '').strip()
    if not text:
        raise ValueError('Annotation text is required.')
    try:
        page_number = int(data.get('page_number') or 1)
    except (TypeError, ValueError):
        page_number = 1
    try:
        x_pct = float(data.get('x') or 50)
        y_pct = float(data.get('y') or 50)
        fontsize = float(data.get('fontsize') or 12)
    except (TypeError, ValueError):
        x_pct, y_pct, fontsize = 50.0, 50.0, 12.0
    x_pct = max(0, min(100, x_pct))
    y_pct = max(0, min(100, y_pct))
    fontsize = max(6, min(72, fontsize))

    output_path = create_output_path('.pdf', 'annotated_')
    pdf = fitz.open(file_path)
    try:
        total = len(pdf)
        if page_number < 1 or page_number > total:
            raise ValueError(f'Page {page_number} does not exist (document has {total} pages).')
        page = pdf[page_number - 1]
        rect = page.rect
        text_width = fitz.get_text_length(text, fontname='helv', fontsize=fontsize)
        x = rect.width * (x_pct / 100.0)
        y = rect.height * (y_pct / 100.0)
        box = fitz.Rect(x, y, x + text_width + 20, y + fontsize + 10)
        box = box & page.rect
        page.insert_textbox(
            box, text, fontsize=fontsize, fontname='helv',
            color=(1, 0, 0), fill_opacity=1, stroke_opacity=1,
            align=fitz.TEXT_ALIGN_LEFT,
        )
        pdf.save(output_path, garbage=3, deflate=True)
    finally:
        pdf.close()
    return output_path


# ---------------------------------------------------------------------------
# Highlight PDF
# ---------------------------------------------------------------------------

HIGHLIGHT_COLORS = {
    'yellow': (1, 1, 0),
    'green': (0, 1, 0),
    'blue': (0, 0, 1),
    'pink': (1, 0.5, 1),
    'orange': (1, 0.65, 0),
}


def highlight_pdf(file_path, data):
    """Highlight occurrences of given words/phrases using color highlights."""
    import fitz

    terms_raw = data.get('words') or ''
    terms = [t.strip() for t in str(terms_raw).replace(';', ',').split(',') if t.strip()]
    if not terms:
        raise ValueError('At least one word or phrase to highlight is required.')
    color_name = data.get('color') or 'yellow'
    color = HIGHLIGHT_COLORS.get(color_name, HIGHLIGHT_COLORS['yellow'])
    try:
        page_number = int(data.get('page_number') or 0)
    except (TypeError, ValueError):
        page_number = 0

    output_path = create_output_path('.pdf', 'highlighted_')
    pdf = fitz.open(file_path)
    try:
        total = len(pdf)
        if page_number > 0 and (page_number < 1 or page_number > total):
            raise ValueError(f'Page {page_number} does not exist (document has {total} pages).')
        target_indices = [page_number - 1] if page_number > 0 else list(range(total))
        for i, page in enumerate(pdf):
            if i not in target_indices:
                continue
            for term in terms:
                try:
                    regions = page.search_for(term)
                except Exception:
                    regions = []
                for rect in regions:
                    page.add_highlight_annot(rect, color=color)
        pdf.save(output_path, garbage=3, deflate=True)
    finally:
        pdf.close()
    return output_path