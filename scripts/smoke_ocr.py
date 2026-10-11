"""Smoke-test the OCR stack from inside Django.

    python -m scripts.smoke_ocr   (run from the project root)

Checks, in order:
  1. Django can import pdf_tools.views and pdf_tools.forms.
  2. The new OcrForm validates and rejects junk page ranges.
  3. tesseract_languages() reports the installed packs.
  4. ocr_pdf() produces a searchable PDF *and* a TXT file for a 1-page scan.
  5. ocr_pdf() handles a 10-page scan without exploding memory.
  6. The /tools/ocr/ page renders and the POST redirects to a result.
"""
import os
import sys
import time
import traceback

import django

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.core.files.uploadedfile import SimpleUploadedFile  # noqa: E402
from django.test import Client  # noqa: E402

from pdf_tools import forms, views  # noqa: E402
from pdf_tools.services.ocr import (  # noqa: E402
    ocr_pdf, tesseract_available, tesseract_languages)

PASS, FAIL = 'PASS', 'FAIL'
results = []

# Lines baked into the generated scans. The checks assert on 'Invoice number',
# so any rewrite of the fixture text must keep that phrase.
SCAN_LINES = [
    'PDF Master OCR Verification',
    '',
    'Invoice number: PM-2026-0042',
    'Total due: 1,250.00 USD',
    'Due date: 2026-11-30',
    '',
    'Signed by: A. Reviewer',
    'Page {n}',
]

ONE_PAGE = 'scan_1page.pdf'
TEN_PAGE = 'scan_10page.pdf'


def make_scan(path, pages, dpi=150, lines=None):
    """Build an image-only (scanned) PDF so the fixtures always exist.

    Pillow renders each page to a PNG and embeds it in the PDF, which is exactly
    what a flatbed scanner produces: pixels with no text layer. Recreating the
    fixtures here keeps this script runnable on a clean checkout.

    ``lines`` overrides :data:`SCAN_LINES`, which is how the Urdu check renders
    Arabic-script text. A font with Arabic coverage is picked when needed.
    """
    from PIL import Image, ImageDraw, ImageFont

    body = SCAN_LINES if lines is None else lines
    needs_arabic = any('\u0600' <= c <= '\u06ff' for line in body for c in line)

    def font(size):
        # Arabic needs a face with real coverage; arial.ttf is Latin-only.
        # Absolute Windows paths are tried first because a bare filename is not
        # resolvable by Pillow unless the font dir happens to be on its path.
        names = (['C:/Windows/Fonts/NotoNaskhArabic-Regular.ttf',
                  'C:/Windows/Fonts/Amiri-Regular.ttf',
                  'C:/Windows/Fonts/NotoSansArabic-Regular.ttf',
                  'NotoNaskhArabic-Regular.ttf', 'Amiri-Regular.ttf']
                 if needs_arabic else [])
        names += ['C:/Windows/Fonts/arial.ttf', 'arial.ttf',
                  'DejaVuSans.ttf', 'segoeui.ttf']
        for name in names:
            try:
                return ImageFont.truetype(name, size)
            except Exception:
                continue
        return ImageFont.load_default()

    def render(no):
        w, h = int(8.27 * dpi), int(11.69 * dpi)
        img = Image.new('RGB', (w, h), 'white')
        draw = ImageDraw.Draw(img)
        draw.rectangle([30, 30, w - 30, h - 30], outline=(190, 190, 190), width=3)
        f = font(34)
        y = 120
        for line in body:
            draw.text((110, y), line.format(n=no), fill='black', font=f)
            y += 70
        return img

    first = render(1)
    first.save(path, save_all=True,
               append_images=[render(n) for n in range(2, pages + 1)],
               format='PDF', resolution=float(dpi))
    print('    fixture: %s (%d pages)' % (path, pages))


def check(label, fn):
    try:
        detail = fn()
        results.append((PASS, label, detail or ''))
        print('[%s] %s %s' % (PASS, label, detail or ''))
    except Exception as exc:
        results.append((FAIL, label, str(exc)))
        print('[%s] %s -> %s' % (FAIL, label, exc))
        traceback.print_exc()


def _imports():
    assert views.ocr_pdf_view and forms.OcrForm
    return 'views+forms import'


def _form():
    langs = ['eng', 'urd', 'fra']
    good = forms.OcrForm({'lang': 'eng', 'lang2': 'urd', 'output': 'both'},
                         available_languages=langs)
    assert good.is_valid(), good.errors
    assert good.cleaned_data['lang'] == 'eng+urd'
    bad = forms.OcrForm({'lang': 'eng', 'output': 'both', 'pages': 'abc'},
                        available_languages=langs)
    assert not bad.is_valid(), 'junk page range was accepted'
    assert 'pages' in bad.errors
    return 'valid form ok, junk range rejected'


def _langs():
    langs = sorted(tesseract_languages())
    assert langs, 'no languages reported'
    for need in ('eng', 'urd'):
        if need not in langs:
            print('       WARNING: %r not installed (found %s)' % (need, langs))
    return 'installed: %s' % ', '.join(langs)


def _ocr_single():
    assert tesseract_available(), 'tesseract binary not available'
    t0 = time.time()
    pdf_out, txt_out = ocr_pdf(ONE_PAGE,
                               {'pages': '', 'lang': 'eng', 'txt': True})
    dt = time.time() - t0
    assert pdf_out and os.path.exists(pdf_out), 'no searchable pdf'
    assert txt_out and os.path.exists(txt_out), 'no txt file'

    import pymupdf
    doc = pymupdf.open(pdf_out)
    layer = doc[0].get_text().strip()
    pages = len(doc)
    doc.close()
    assert 'Invoice number' in layer, 'text layer missing: %r' % layer[:80]
    with open(txt_out, encoding='utf-8') as fh:
        txt = fh.read()
    assert 'Invoice number' in txt, 'txt missing content'
    for p in (pdf_out, txt_out):
        os.remove(p)
    return '%d page, %.1fs, layer %d chars, txt %d chars' % (
        pages, dt, len(layer), len(txt))


def _ocr_ten():
    t0 = time.time()
    pdf_out, _ = ocr_pdf(TEN_PAGE,
                         {'pages': '', 'lang': 'eng', 'txt': False})
    dt = time.time() - t0
    assert pdf_out and os.path.exists(pdf_out)
    import pymupdf
    doc = pymupdf.open(pdf_out)
    pages = len(doc)
    words = sum(len(doc[i].get_text().split()) for i in range(pages))
    doc.close()
    os.remove(pdf_out)
    assert words > 50, 'only %d words recovered from 10 pages' % words
    return '%d pages in %.1fs, %d words recovered' % (pages, dt, words)


def _web():
    with open(ONE_PAGE, 'rb') as fh:
        payload = fh.read()
    client = Client()
    get = client.get('/tools/ocr/')
    assert get.status_code == 200, 'GET /tools/ocr/ -> %s' % get.status_code
    assert b'Start OCR' in get.content, 'submit button missing'
    assert b'English + Urdu' in get.content, 'language selector missing'
    post = client.post('/tools/ocr/', {
        'file': SimpleUploadedFile('scan.pdf', payload,
                                   content_type='application/pdf'),
        'pages': '', 'lang': 'eng', 'output': 'both'})
    assert post.status_code == 200, 'POST -> %s' % post.status_code
    assert b'OCR finished' in post.content, 'no result screen'
    assert b'Download searchable PDF' in post.content, 'no PDF download link'
    assert b'Download TXT' in post.content, 'no TXT download link'
    return 'GET 200, POST shows both downloads'


def main():
    print('=' * 70)
    print('OCR SMOKE TEST')
    print('=' * 70)
    # Fixtures are generated rather than committed, so this script always has
    # valid input. Regenerated on every run to prove reproducibility.
    for path, pages in ((ONE_PAGE, 1), (TEN_PAGE, 10)):
        try:
            make_scan(path, pages)
        except Exception as exc:      # noqa: BLE001 - report and keep going
            print('    WARNING: could not build %s (%s)' % (path, exc))
    check('1. imports', _imports)
    check('2. OcrForm', _form)
    check('3. tesseract languages', _langs)
    check('4. OCR 1-page scan (pdf+txt)', _ocr_single)
    check('5. OCR 10-page scan', _ocr_ten)
    check('6. web view', _web)
    print('-' * 70)
    failed = [r for r in results if r[0] == FAIL]
    print('%d passed, %d failed' % (len(results) - len(failed), len(failed)))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())

