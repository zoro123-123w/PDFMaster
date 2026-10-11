"""Smoke tests for STEP 2 tools: Compress PDF quality levels, ZIP tools, PDF to Text.

Run:  .\\venv\\Scripts\\python.exe scripts\\verify_tools.py
Exits non-zero if any check fails.
"""
import io
import os
import sys
import zipfile

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
os.environ.setdefault('SECRET_KEY', 'verify-tools-key')
os.environ.setdefault('DEBUG', 'True')
os.environ.setdefault('ALLOWED_HOSTS', 'testserver,127.0.0.1,localhost')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import django
django.setup()

import pymupdf
from django.test import Client
from django.core.files.uploadedfile import SimpleUploadedFile

from pdf_tools.services.compress import compress_pdf_service, QUALITY_PRESETS
from pdf_tools.services.pdf_to_text import pdf_to_text_service
from pdf_tools.services.zip_tools import (
    compress_files, list_zip_contents, extract_zip, ZipSecurityError,
)

FAILURES = []


def check(name, cond, detail=''):
    status = 'PASS' if cond else 'FAIL'
    print(f'[{status}] {name}' + (f' -- {detail}' if detail and not cond else ''))
    if not cond:
        FAILURES.append(name)


def make_image_pdf(path, pages=3, img_px=1200):
    """Create a PDF with large photos (compressible) + text."""
    import PIL.Image as PILImage
    import PIL.ImageDraw as PILDraw
    im = PILImage.new('RGB', (img_px, img_px), (180, 90, 40))
    d = PILDraw.Draw(im)
    for i in range(0, img_px, 40):  # some structure
        d.line([(i, 0), (0, i)], fill=(20, 20, 20), width=3)
    buf = io.BytesIO()
    im.save(buf, format='JPEG', quality=95)
    img_bytes = buf.getvalue()
    doc = pymupdf.open()
    for i in range(pages):
        page = doc.new_page(width=595, height=842)
        page.insert_text((72, 100), f'Smoke test page {i + 1}', fontsize=16)
        page.insert_image(pymupdf.Rect(50, 150, 545, 640), stream=img_bytes)
    doc.save(path)
    doc.close()


def test_compress_levels():
    tmp = os.path.join(os.environ.get('TEMP', '.'), 'smoke_compress.pdf')
    make_image_pdf(tmp)
    sizes = {}
    for q in QUALITY_PRESETS:
        out = compress_pdf_service(tmp, quality=q)
        sizes[q] = os.path.getsize(out)
        # Verify output is a valid PDF with same page count.
        d = pymupdf.open(out)
        check(f'compress {q}: valid pdf, 3 pages', d.page_count == 3)
        d.close()
        os.remove(out)
    check('compress medium < low', sizes['medium'] < sizes['low'],
          f"medium={sizes['medium']} low={sizes['low']}")
    check('compress high <= medium', sizes['high'] <= sizes['medium'],
          f"high={sizes['high']} medium={sizes['medium']}")
    # Unknown quality falls back to low without error.
    out = compress_pdf_service(tmp, quality='bogus')
    check('compress unknown quality falls back', os.path.getsize(out) > 0)
    os.remove(out)
    os.remove(tmp)


def test_zip_tools():
    import shutil
    tmpdir = os.path.join(os.environ.get('TEMP', '.'), 'smoke_zip')
    os.makedirs(tmpdir, exist_ok=True)
    files = []
    for i, name in enumerate(['a.txt', 'b.txt', 'c.txt']):
        p = os.path.join(tmpdir, name)
        with open(p, 'w') as f:
            f.write('hello ' * 500 * (i + 1))
        files.append(p)
    zpath, zname = compress_files([(p, os.path.basename(p)) for p in files],
                                  level='maximum', zip_name='smoke')
    check('zip compress creates archive', os.path.exists(zpath))
    summary = list_zip_contents(zpath)
    check('zip list counts 3 entries', summary['count'] == 3, str(summary))
    check('zip list has sizes', summary['uncompressed'] > 0)
    out_dir, out_paths, _ = extract_zip(zpath)
    check('zip extract writes 3 files', len(out_paths) == 3)
    # Zip-slip rejection.
    bad = os.path.join(tmpdir, 'evil.zip')
    with zipfile.ZipFile(bad, 'w') as zf:
        zf.writestr('../evil.txt', 'nope')
    try:
        list_zip_contents(bad)
        check('zip-slip rejected', False, 'no exception raised')
    except ZipSecurityError:
        check('zip-slip rejected', True)
    shutil.rmtree(tmpdir, ignore_errors=True)
    try:
        os.remove(zpath)
        os.remove(bad)
    except OSError:
        pass


def test_pdf_to_text():
    tmp = os.path.join(os.environ.get('TEMP', '.'), 'smoke_p2t.pdf')
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 100), 'Hello PDF Master text layer!', fontsize=14)
    doc.save(tmp)
    doc.close()
    out = pdf_to_text_service(tmp)
    with open(out, 'r', encoding='utf-8') as f:
        text = f.read()
    check('pdf_to_text extracts text', 'Hello PDF Master' in text, text[:80])
    os.remove(tmp)
    os.remove(out)


def test_views():
    """Exercise the new URLs plus compress through the Django test client."""
    client = Client()
    for url in ['/tools/zip-compress/', '/tools/zip-extract/',
                '/tools/pdf-to-text/', '/tools/compress-pdf/']:
        r = client.get(url)
        check(f'GET {url} -> 200', r.status_code == 200, str(r.status_code))
    # ZIP compress POST.
    up = SimpleUploadedFile('files.txt', b'x' * 5000, content_type='text/plain')
    r = client.post('/tools/zip-compress/',
                    {'files': [up], 'level': 'normal', 'zip_name': 'test.zip'})
    check('POST zip-compress renders result',
          r.status_code == 200 and b'Archive ready' in r.content,
          str(r.status_code))
    # ZIP extract POST (list).
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as zf:
        zf.writestr('inner.txt', 'content here')
    r = client.post('/tools/zip-extract/',
                    {'file': SimpleUploadedFile('t.zip', buf.getvalue(),
                                                content_type='application/zip')})
    check('POST zip-extract lists inner.txt',
          r.status_code == 200 and b'inner.txt' in r.content,
          str(r.status_code))
    # PDF to text POST -> downloads txt (FileResponse streams the bytes).
    pdf_buf = io.BytesIO()
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 100), 'view smoke text')
    doc.save(pdf_buf)
    doc.close()
    r = client.post('/tools/pdf-to-text/',
                    {'file': SimpleUploadedFile('s.pdf', pdf_buf.getvalue(),
                                                content_type='application/pdf')},
                    follow=True)
    body = b''.join(r.streaming_content) if getattr(r, 'streaming', False) else r.content
    check('POST pdf-to-text downloads txt',
          r.status_code == 200 and b'view smoke text' in body,
          str(r.status_code))
    # Compress POST with quality=high.
    img_pdf = os.path.join(os.environ.get('TEMP', '.'), 'smoke_view.pdf')
    make_image_pdf(img_pdf, pages=2)
    with open(img_pdf, 'rb') as f:
        r = client.post('/tools/compress-pdf/',
                        {'file': SimpleUploadedFile('c.pdf', f.read(),
                                                    content_type='application/pdf'),
                         'quality': 'high'})
    check('POST compress (high) renders result',
          r.status_code == 200 and b'Compression Complete' in r.content,
          str(r.status_code))
    check('compress result shows reduction', b'Reduction' in r.content)
    os.remove(img_pdf)


if __name__ == '__main__':
    test_compress_levels()
    test_zip_tools()
    test_pdf_to_text()
    test_views()
    print()
    if FAILURES:
        print(f'{len(FAILURES)} FAILURE(S): {FAILURES}')
        sys.exit(1)
    print('ALL CHECKS PASSED')

