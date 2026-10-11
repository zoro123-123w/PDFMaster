"""Confirm the Urdu TXT download is real UTF-8, not mojibake.

The PowerShell console garbles Arabic on cp1252, so a "wrong looking" first line
in the terminal proves nothing. This compares code points against the known
source sentence and writes a report we can read reliably.
"""
import os
import sys

import django

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
os.environ.setdefault('SECRET_KEY', 'utf8-key')
os.environ.setdefault('DEBUG', 'True')
os.environ.setdefault('ALLOWED_HOSTS', 'testserver')
django.setup()

from django.core.files.uploadedfile import SimpleUploadedFile  # noqa: E402
from django.test import Client  # noqa: E402
from scripts.smoke_ocr import make_scan  # noqa: E402
from pdf_tools.services.ocr import tesseract_available  # noqa: E402

# "PDF Master OCR Verification" plus a real Urdu sentence, rendered onto a scan.
URDU = '\u067e\u0627\u06a9\u0633\u062a\u0627\u0646 \u06a9\u06cc\u0628\u0648\u0631\u0688'


def main():
    print('tesseract_available:', tesseract_available())
    make_scan('urdu_probe.pdf', 1,
              lines=['PDF Master OCR Verification', '', URDU])
    path = 'urdu_probe.pdf'
    print('sample scan:', path)

    with open(path, 'rb') as fh:
        payload = fh.read()
    client = Client()
    resp = client.post('/tools/ocr/',
                       {'file': SimpleUploadedFile('urdu_probe.pdf', payload,
                                                  content_type='application/pdf'),
                        'pages': '', 'lang': 'urd', 'lang2': '', 'output': 'txt'})
    html = resp.content.decode('utf-8')
    # The result screen shows a link per output. Pick the one whose filename
    # ends in .txt so we never accidentally download the searchable PDF.
    import re
    txt_id = None
    for jid in re.findall(r'/tools/download/([0-9a-f-]{36})/', html):
        dl = client.get('/tools/download/%s/' % jid)
        if 'text/plain' in (dl.get('Content-Type') or ''):
            txt_id = jid
            break
    if not txt_id:
        print('no TXT download link found')
        print(html[-2000:])
        return 1
    dl = client.get('/tools/download/%s/' % txt_id)
    raw = b''.join(dl.streaming_content)
    report = []
    report.append('txt bytes      : %d' % len(raw))
    report.append('content-type   : %s' % dl.get('Content-Type'))
    report.append('has UTF-8 BOM  : %s' % raw.startswith(b'\xef\xbb\xbf'))
    # A BOM is written on purpose so Windows Notepad renders Urdu correctly.
    text = raw.decode('utf-8-sig')
    report.append('urdu source cp : %s'
                  % ' '.join('%04X' % ord(c) for c in URDU))
    report.append('recognised     : %r' % text)
    report.append('arabic chars   : %s'
                  % any('\u0600' <= c <= '\u06ff' for c in text))
    with open('urdu_utf8_report.txt', 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(report) + '\n')
    print('report written to urdu_utf8_report.txt')
    for line in report:
        print(line)
    try:
        os.remove(path)
    except OSError:
        pass
    return 0


if __name__ == '__main__':
    sys.exit(main())
