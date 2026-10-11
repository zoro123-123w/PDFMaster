"""Does the Urdu Tesseract pack actually work?

The fixture scan is rendered by Pillow. If Pillow shapes Arabic via Raqm the
image is real joined Urdu and Tesseract should read it back. This bypasses the
web layer entirely and tests the OCR engine on a known-good shaped render.
"""
import os
import sys

import django

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
os.environ.setdefault('SECRET_KEY', 'urd-key')
django.setup()

import pymupdf  # noqa: E402
import pytesseract  # noqa: E402
from PIL import features  # noqa: E402
from PIL import Image  # noqa: E402

# "Pakistan Cyber" - three words, base codepoints below.
URDU = '\u067e\u0627\u06a9\u0633\u062a\u0627\u0646 \u0633\u0627\u0626\u06cc\u0628\u0631'
FONT = r'C:\Windows\Fonts\NotoNaskhArabic-Regular.ttf'


def main():
    report = []
    report.append('Pillow raqm (Arabic shaping): %s' % features.check('raqm'))

    doc = pymupdf.open()
    page = doc.new_page()
    font = pymupdf.Font(fontfile=FONT)
    tw = pymupdf.TextWriter(page.rect)
    tw.append((60, 100), URDU, font=font, fontsize=28)
    tw.write_text(page)
    pix = page.get_pixmap(dpi=300)
    doc.close()
    img = Image.open(io.BytesIO(pix.tobytes('png')))

    report.append('source codepoints: %s'
                  % ' '.join('%04X' % ord(c) for c in URDU))
    for lang in ('urd', 'eng+urd'):
        out = pytesseract.image_to_string(img, lang=lang).strip()
        report.append('%s -> %r' % (lang, out))
        report.append('   arabic-script chars recognised: %s'
                      % sum(1 for c in out if '\u0600' <= c <= '\u06ff'))
    with open('urdu_pack_report.txt', 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(report) + '\n')
    for line in report:
        print(line)


import io  # noqa: E402

if __name__ == '__main__':
    main()
