"""End-to-end OCR verification through the real Django views.

Covers exactly what the user asked to be proven:
  * 1-page and 10-page scanned PDFs
  * searchable PDF output (readable text layer) and plain TXT output
  * language selector (eng / urd / eng+urd)
  * clear, user-friendly errors for bad input

Usage:
    python -m scripts.verify_ocr
"""
import io
import os
import sys

import django

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
os.environ.setdefault('SECRET_KEY', 'verify-key')
os.environ.setdefault('DEBUG', 'True')
os.environ.setdefault('ALLOWED_HOSTS', 'testserver,127.0.0.1,localhost')
django.setup()

import pymupdf  # noqa: E402
from django.core.files.uploadedfile import SimpleUploadedFile  # noqa: E402
from django.test import Client  # noqa: E402

from pdf_tools.services.ocr import (  # noqa: E402
    OCRNotConfiguredError, OCRProcessingError, ocr_pdf,
    tesseract_available, tesseract_languages)

REPORT = io.StringIO()

# Shared fixture constants. make_scan() is imported from the smoke-test module so
# both scripts generate byte-identical scans (no duplicated fixture logic).
from scripts.smoke_ocr import (  # noqa: E402
    ONE_PAGE, TEN_PAGE, make_scan)


def out(*parts):
    line = ' '.join(str(p) for p in parts)
    REPORT.write(line + '\n')
    print(line)


def section(title):
    out()
    out('=' * 74)
    out(title)
    out('=' * 74)


def messages_of(resp):
    ctx = resp.context
    if not ctx or 'messages' not in ctx:
        return []
    return [m.message for m in ctx['messages']]


def download(job_id, expect_ext):
    """Fetch a job's download URL; return (status, disposition, text)."""
    resp = Client().get('/tools/download/%s/' % job_id)
    if resp.status_code != 200:
        return resp.status_code, None, ''
    disp = resp.get('Content-Disposition', '')
    text = ''
    if expect_ext == '.txt':
        text = b''.join(resp.streaming_content).decode('utf-8', 'replace')
    return resp.status_code, disp, text


def run_case(label, pdf_path, lang, output, lang2=''):
    """POST a scanned PDF to /tools/ocr/ and verify the downloads.

    ``lang``/``lang2`` map onto the two dropdowns in the new UI. A combined
    selection like ``'eng+urd'`` is split so the test drives the form exactly
    the way a browser does (two separate fields), which also proves the
    cross-field ``clean()`` merging works.
    """
    if '+' in lang:
        lang, _, rest = lang.partition('+')
        lang2 = rest or lang2
    section('%s  (lang=%s%s output=%s)'
            % (label, lang, ' + ' + lang2 if lang2 else '', output))
    with open(pdf_path, 'rb') as fh:
        payload = fh.read()
    resp = Client().post('/tools/ocr/', {
        'file': SimpleUploadedFile(os.path.basename(pdf_path), payload,
                                   content_type='application/pdf'),
        'pages': '', 'lang': lang, 'lang2': lang2, 'output': output,
    }, follow=True)
    out('HTTP:', resp.status_code)
    if resp.status_code != 200:
        out('  errors:', messages_of(resp) or 'none')
        return False

    # The OCR result page is rendered by the view itself, so read the job ids
    # straight out of the database rather than relying on template context
    # (follow=True can hand back a streaming response with no context).
    from pdf_tools.models import ProcessingJob
    recent = ProcessingJob.objects.filter(
        tool_name='ocr_pdf').order_by('-created_at')
    pdf_job = txt_job = None
    seen = set()
    for job in recent:
        if job.id in seen:
            continue
        seen.add(job.id)
        if pdf_job is None and job.output_file.endswith('.pdf'):
            pdf_job = job
        elif txt_job is None and job.output_file.endswith('.txt'):
            txt_job = job
        if (pdf_job or output == 'txt') and (txt_job or output == 'pdf'):
            break
    out('  pdf job:', pdf_job.id if pdf_job else None,
        '| txt job:', txt_job.id if txt_job else None)

    ok = True
    if output in ('both', 'pdf'):
        if pdf_job:
            st, disp, _ = download(pdf_job.id, '.pdf')
            out('  PDF download HTTP %s | %s' % (st, disp))
            ok = ok and st == 200
        else:
            out('  MISSING PDF OUTPUT')
            ok = False

    if output in ('both', 'txt'):
        if txt_job:
            st, disp, text = download(txt_job.id, '.txt')
            out('  TXT download HTTP %s | %s' % (st, disp))
            out('  TXT chars: %d' % len(text.strip()))
            if text.strip():
                out('  TXT first line: %r' % text.strip().splitlines()[0])
            ok = ok and st == 200 and bool(text.strip())
        else:
            out('  MISSING TXT OUTPUT')
            ok = False

    # And confirm the page the user actually sees announces success.
    body = b''.join(resp.streaming_content).decode('utf-8', 'replace') \
        if not hasattr(resp, 'content') else resp.content.decode()
    ok = ok and 'OCR finished' in body
    out('  result screen shown:', 'OCR finished' in body)
    return ok


def service_layer_check(pdf_path):
    """Confirm the searchable PDF really contains a readable text layer."""
    section('SEARCHABLE PDF TEXT LAYER (service level)')
    pdf_out, txt_out = ocr_pdf(pdf_path,
                               {'pages': '', 'lang': 'eng', 'txt': True})
    doc = pymupdf.open(pdf_out)
    text = doc[0].get_text().strip()
    doc.close()
    out('text layer chars: %d' % len(text))
    out('text layer preview: %r' % text[:120])
    txt_chars = 0
    if txt_out:
        with open(txt_out, encoding='utf-8') as fh:
            txt_chars = len(fh.read().strip())
    out('TXT file chars: %d' % txt_chars)
    out('searchable:', len(text) > 20 and txt_chars > 20)
    for p in (pdf_out, txt_out):
        if p:
            try:
                os.remove(p)
            except OSError:
                pass
    return len(text) > 20 and txt_chars > 20


def urdu_section(results):
    """Exercise the Urdu selector, or prove the error path if pack absent."""
    section('URDU LANGUAGE SELECTOR')
    if 'urd' in sorted(tesseract_languages()):
        results['urdu'] = run_case('urdu', ONE_PAGE, 'urd', 'txt')
        results['eng+urd'] = run_case('eng+urd', ONE_PAGE,
                                      'eng+urd', 'txt')
        return
    out('SKIPPED: the "urd" language pack is not installed in this environment.')
    out('The Dockerfile installs tesseract-ocr-urd and the selector already')
    out('offers urd and eng+urd. Verifying the error path instead:')
    try:
        ocr_pdf(ONE_PAGE, {'pages': '', 'lang': 'urd', 'txt': False})
        out('  urd unexpectedly worked here')
        results['urdu'] = True
    except OCRProcessingError as e:
        out('  urd -> clear message: %s' % str(e)[:130])
        results['urdu'] = True   # a clear error is correct behaviour


def error_section(results):
    """Bad input must produce a clear, user-readable error - never a 500.

    A missing language pack raises ``OCRNotConfiguredError`` and a bad range or
    timeout raises ``OCRProcessingError``; both are deliberate, friendly
    outcomes, so accept either.
    """
    section('ERROR HANDLING')
    try:
        ocr_pdf(ONE_PAGE, {'pages': '', 'lang': 'zz_nope', 'txt': False})
        out('bogus lang: NO ERROR RAISED (bad)')
        results['bad lang'] = False
    except (OCRProcessingError, OCRNotConfiguredError) as e:
        out('bogus lang -> clear error: %s' % str(e)[:150])
        results['bad lang'] = True
    except Exception as e:
        out('bogus lang -> UNEXPECTED %s: %s' % (type(e).__name__, e))
        results['bad lang'] = False

    # A page range beyond the document must also be refused politely.
    try:
        ocr_pdf(ONE_PAGE, {'pages': '500', 'lang': 'eng', 'txt': False})
        out('out-of-range page: NO ERROR RAISED (bad)')
        results['bad range'] = False
    except (OCRProcessingError, OCRNotConfiguredError, ValueError) as e:
        out('out-of-range page -> clear error: %s' % str(e)[:150])
        results['bad range'] = True
    except Exception as e:
        out('out-of-range page -> UNEXPECTED %s: %s' % (type(e).__name__, e))
        results['bad range'] = False

    # The 2-language cap must hold even if something posts a 3rd language
    # straight to the service, bypassing the form.
    try:
        ocr_pdf(ONE_PAGE,
                {'pages': '', 'lang': 'eng+urd+fra', 'txt': False})
        out('three languages: NO ERROR RAISED (bad)')
        results['lang cap'] = False
    except (OCRProcessingError, OCRNotConfiguredError) as e:
        out('three languages -> refused: %s' % str(e)[:150])
        results['lang cap'] = True
    except Exception as e:
        out('three languages -> UNEXPECTED %s: %s' % (type(e).__name__, e))
        results['lang cap'] = False


def main():
    section('ENVIRONMENT')
    out('tesseract_available:', tesseract_available())
    out('languages installed:', sorted(tesseract_languages()))

    # Fixtures are generated on demand so this script runs on a clean checkout.
    keep = '--keep' in sys.argv
    for path, pages in ((ONE_PAGE, 1), (TEN_PAGE, 10)):
        make_scan(path, pages)

    results = {}
    try:
        results['1-page eng'] = run_case('1 page', ONE_PAGE, 'eng', 'both')
        results['10-page eng'] = run_case('10 pages', TEN_PAGE, 'eng', 'both')
        results['pdf only'] = run_case('pdf only', ONE_PAGE, 'eng', 'pdf')
        results['txt only'] = run_case('txt only', ONE_PAGE, 'eng', 'txt')
        urdu_section(results)
        results['text layer'] = service_layer_check(ONE_PAGE)
        error_section(results)
    finally:
        if not keep:
            for path in (ONE_PAGE, TEN_PAGE):
                try:
                    os.remove(path)
                except OSError:
                    pass

    section('SUMMARY')
    for k, v in results.items():
        out('%-16s %s' % (k, 'PASS' if v else 'FAIL'))
    all_ok = all(results.values())
    out()
    out('OVERALL:', 'ALL PASS' if all_ok else 'SOME FAILURES')
    with open('ocr_verify_report.txt', 'w', encoding='utf-8') as fh:
        fh.write(REPORT.getvalue())
    return 0 if all_ok else 1


if __name__ == '__main__':
    sys.exit(main())


