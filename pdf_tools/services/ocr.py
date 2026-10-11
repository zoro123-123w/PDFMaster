"""OCR service.

Uses Tesseract (via pytesseract) on page images rendered by PyMuPDF, so Poppler
is not required for OCR. FIXED (2026-10): the resolved Tesseract path is now
actually handed to pytesseract, real Tesseract errors are surfaced instead of
being flattened, RAM is released per page, and a TXT output is supported.
"""
import io
import logging
import os
import subprocess
import sys
from django.conf import settings

from .utils import create_output_path

logger = logging.getLogger(__name__)


class OCRNotConfiguredError(Exception):
    """Raised when the Tesseract binary is not available."""


class OCRProcessingError(Exception):
    """Raised for user-fixable OCR problems (too big, too many pages, timeout)."""


# Hard limits. The server may only have 512 MB, so OCR is capped conservatively.
OCR_MAX_PAGES = int(getattr(settings, 'OCR_MAX_PAGES', 30) or 30)
OCR_MAX_FILE_SIZE = int(
    getattr(settings, 'OCR_MAX_FILE_SIZE', 20 * 1024 * 1024) or 20 * 1024 * 1024)
OCR_DPI = int(getattr(settings, 'OCR_DPI', 200) or 200)
OCR_PAGE_TIMEOUT = int(getattr(settings, 'OCR_PAGE_TIMEOUT', 60) or 60)

# How many language packs a single run may combine. Each extra pack costs RAM and
# CPU on every page, so this is capped rather than left open.
OCR_MAX_LANGS = int(getattr(settings, 'OCR_MAX_LANGS', 2) or 2)

# Human labels for the languages users actually pick. Anything not listed is
# shown by its raw Tesseract code, because the installed set changes with the
# image and hardcoding 130 names would drift out of date.
OCR_LANG_LABELS = {
    'eng': 'English', 'urd': 'Urdu', 'ara': 'Arabic', 'fas': 'Persian',
    'pus': 'Pashto', 'snd': 'Sindhi', 'hin': 'Hindi', 'ben': 'Bengali',
    'tam': 'Tamil', 'tel': 'Telugu', 'kan': 'Kannada', 'mal': 'Malayalam',
    'mar': 'Marathi', 'guj': 'Gujarati', 'pan': 'Punjabi', 'nep': 'Nepali',
    'sin': 'Sinhala', 'san': 'Sanskrit', 'ori': 'Odia', 'asm': 'Assamese',
    'fra': 'French', 'deu': 'German', 'spa': 'Spanish', 'ita': 'Italian',
    'por': 'Portuguese', 'nld': 'Dutch', 'swe': 'Swedish', 'nor': 'Norwegian',
    'dan': 'Danish', 'fin': 'Finnish', 'pol': 'Polish', 'ces': 'Czech',
    'slk': 'Slovak', 'hun': 'Hungarian', 'ron': 'Romanian', 'bul': 'Bulgarian',
    'ell': 'Greek', 'tur': 'Turkish', 'rus': 'Russian', 'ukr': 'Ukrainian',
    'heb': 'Hebrew', 'yid': 'Yiddish', 'jpn': 'Japanese', 'chi_sim': 'Chinese (Simplified)',
    'chi_tra': 'Chinese (Traditional)', 'kor': 'Korean', 'tha': 'Thai',
    'vie': 'Vietnamese', 'ind': 'Indonesian', 'msa': 'Malay', 'tgl': 'Filipino',
    'khm': 'Khmer', 'lao': 'Lao', 'mya': 'Burmese', 'kat': 'Georgian',
    'hye': 'Armenian', 'kaz': 'Kazakh', 'aze': 'Azerbaijani', 'uzb': 'Uzbek',
    'alb': 'Albanian', 'hrv': 'Croatian', 'srp': 'Serbian', 'slv': 'Slovenian',
    'est': 'Estonian', 'lav': 'Lithuanian', 'lit': 'Lithuanian (old)',
    'sqi': 'Albanian (alt)', 'eus': 'Basque', 'cat': 'Catalan', 'glg': 'Galician',
    'isl': 'Icelandic', 'gle': 'Irish', 'cym': 'Welsh', 'mlt': 'Maltese',
    'afr': 'Afrikaans', 'swa': 'Swahili', 'amh': 'Amharic', 'yor': 'Yoruba',
}


def language_label(code):
    """Return a friendly label for a Tesseract code (falls back to the code)."""
    if code in OCR_LANG_LABELS:
        return '%s (%s)' % (OCR_LANG_LABELS[code], code)
    return code


def normalize_langs(*values):
    """Join the submitted language selections into one Tesseract ``lang`` string.

    The UI offers up to :data:`OCR_MAX_LANGS` dropdowns (primary + optional
    second language). Tesseract wants them as ``"eng+urd"``. Duplicates and
    blanks are dropped so selecting the same pack twice cannot happen, and the
    result is validated later by :func:`_check_language_available`.

    Returns ``'eng'`` when nothing usable was submitted, so OCR always has a
    language rather than silently defaulting to whatever Tesseract picks.
    """
    parts = []
    for value in values:
        for chunk in str(value or '').split('+'):
            chunk = chunk.strip()
            if chunk and chunk not in parts:
                parts.append(chunk)
    if not parts:
        return 'eng'
    return '+'.join(parts[:OCR_MAX_LANGS])

# Resolved once per process; None until the first successful probe.
_TESSERACT_BINARY = None


def _resolve_tesseract_cmd():
    """Return the Tesseract binary to use: explicit config, then common paths."""
    configured = getattr(settings, 'TESSERACT_CMD', '') or ''
    if configured and os.path.exists(configured):
        return configured
    windows_defaults = [
        r'C:\Program Files\Tesseract-OCR\tesseract.exe',
        r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
    ]
    if sys.platform.startswith('win'):
        for candidate in windows_defaults:
            if os.path.exists(candidate):
                return candidate
    return 'tesseract'


def _configure_pytesseract():
    """Point pytesseract at the resolved binary and return it.

    BUG FIXED: the old code computed the path and then never assigned it to
    ``pytesseract.pytesseract.tesseract_cmd``, so ``TESSERACT_CMD`` and the
    Windows autodetect were dead code. pytesseract always shelled out to a bare
    ``tesseract`` and depended entirely on PATH.
    """
    global _TESSERACT_BINARY
    import pytesseract

    if _TESSERACT_BINARY is None:
        _TESSERACT_BINARY = _resolve_tesseract_cmd()
    pytesseract.pytesseract.tesseract_cmd = _TESSERACT_BINARY
    return _TESSERACT_BINARY


def tesseract_available():
    """Return True if a usable Tesseract binary is present.

    Verifies the binary actually runs (not merely that a path exists) so the UI
    never claims OCR works when the next call would fail.
    """
    import shutil

    cmd = _resolve_tesseract_cmd()
    if not cmd:
        return False
    if os.path.exists(cmd):
        pass
    elif not shutil.which(cmd):
        return False
    try:
        subprocess.run([cmd, '--version'], capture_output=True, timeout=15,
                       check=False)
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def tesseract_languages():
    """Return the list of installed Tesseract language packs (empty on error)."""
    cmd = _resolve_tesseract_cmd()
    try:
        out = subprocess.run([cmd, '--list-langs'], capture_output=True,
                             timeout=20, text=True, check=False)
        if out.returncode != 0:
            return []
        langs = []
        for line in out.stdout.splitlines():
            line = line.strip()
            if line and not line.lower().startswith('list of'):
                langs.append(line)
        return langs
    except (OSError, subprocess.SubprocessError):
        return []


def _check_language_available(lang, available):
    """Validate every requested language code against the installed packs.

    Also enforces the 2-language cap: combining more packs multiplies both RAM
    and per-page CPU time, which is exactly what a 512 MB server cannot afford.
    """
    if not available:
        return  # cannot verify; let Tesseract produce the real error
    parts = [p.strip() for p in (lang or '').split('+') if p.strip()]
    if len(parts) > OCR_MAX_LANGS:
        raise OCRProcessingError(
            'Select at most %d languages at a time. You chose %d (%s). Combining '
            'more packs multiplies memory and processing time on this server.'
            % (OCR_MAX_LANGS, len(parts), lang))
    missing = [part for part in parts if part not in available]
    if missing:
        raise OCRNotConfiguredError(
            "The '%s' language pack is not installed on this server, so '%s' "
            "cannot be recognised. Installed packs: %s."
            % ("', '".join(missing), lang, ', '.join(sorted(available))))


# Cached Arabic-capable font candidates. Windows paths are checked first for
# local development; the Docker image installs the Debian/Noto equivalents.
_ARABIC_FONT_CANDIDATES = [
    r'C:\Windows\Fonts\NotoNaskhArabic-Regular.ttf',
    r'C:\Windows\Fonts\Amiri-Regular.ttf',
    r'C:\Windows\Fonts\NotoSansArabic-Regular.ttf',
    '/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf',
    '/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf',
    '/usr/share/fonts/truetype/amiri/amiri-regular.ttf',
    '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
]
_ARABIC_FONT_CACHE = None


def _arabic_font_path():
    """Return the first existing Arabic-capable TTF, or None (cached)."""
    global _ARABIC_FONT_CACHE
    if _ARABIC_FONT_CACHE is not None:
        return _ARABIC_FONT_CACHE or None
    _ARABIC_FONT_CACHE = ''
    for candidate in _ARABIC_FONT_CANDIDATES:
        if os.path.exists(candidate):
            _ARABIC_FONT_CACHE = candidate
            break
    return _ARABIC_FONT_CACHE or None


def _has_arabic(text):
    """True if the text contains Arabic-script codepoints."""
    return any('\u0600' <= ch <= '\u06ff' or '\u0750' <= ch <= '\u077f'
               or '\ufb50' <= ch <= '\ufdff' for ch in text)


def _write_invisible_layer(page, text, is_rtl=False):
    """Write ``text`` as an invisible (render_mode=3) text layer on ``page``.

    BUG FIXED: ``insert_textbox`` writes NOTHING when the text does not fit and
    returns a negative number, which silently discarded the whole OCR layer on
    dense pages. Here we write line by line with ``insert_text`` and stop at the
    bottom margin, so a full page can never lose its text.

    Arabic-script text uses an embedded Naskh font when one is found, because the
    base-14 'helv' font has no Arabic glyphs and would store garbage.
    """
    fontname = 'helv'
    fontfile = _arabic_font_path() if is_rtl else None
    if fontfile:
        try:
            page.insert_font(fontname='F_arab', fontfile=fontfile)
            fontname = 'F_arab'
        except Exception:
            logger.warning('could not embed Arabic font %s', fontfile,
                           exc_info=True)

    lines = text.splitlines()
    y = 42.0
    bottom = page.rect.height - 30.0
    for index, line in enumerate(lines):
        if y > bottom:
            logger.warning('page full: dropped %d remaining OCR lines',
                           len(lines) - index)
            break
        if line.strip():
            try:
                page.insert_text((40, y), line, fontsize=8.5,
                                 fontname=fontname, render_mode=3)
            except Exception:
                # One unprintable line must not abort the whole document.
                logger.debug('skipped unprintable OCR line', exc_info=True)
        y += 11.0



def _cleanup(paths):
    """Best-effort removal of temp outputs."""
    for path in paths:
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                logger.debug('could not remove temp file %s', path, exc_info=True)


def ocr_pdf(file_path, data=None):
    """Render each requested page, OCR it, and return ``(pdf_path, txt_path)``.

    ``txt_path`` is ``None`` unless ``data['txt']`` is truthy. The PDF always
    receives an invisible text layer so it becomes searchable.

    Memory strategy (the server may have only 512 MB): one page at a time at
    200 DPI, the rendered image dropped immediately, and ``TOOLS.store_shrink``
    called so PyMuPDF's store is trimmed. Without that, the render cache grows
    ~6 MB per page (measured: ~91 MB for 10 pages) and a 30 page scan is OOM
    killed before it finishes.
    """
    data = data or {}

    if not tesseract_available():
        raise OCRNotConfiguredError(
            'OCR is not configured on this server. Install Tesseract '
            '(tesseract-ocr, tesseract-ocr-eng, tesseract-ocr-urd) and set '
            'TESSERACT_CMD if the binary is not on PATH.')

    # Size limits are checked first so we never spend RAM on a refused file.
    try:
        file_size = os.path.getsize(file_path)
    except OSError as exc:
        raise OCRProcessingError('Could not read the uploaded file.') from exc
    if file_size > OCR_MAX_FILE_SIZE:
        raise OCRProcessingError(
            'This file is %.1f MB. OCR is limited to %d MB per file to keep the '
            'server stable - please split it first.'
            % (file_size / (1024 * 1024), OCR_MAX_FILE_SIZE // (1024 * 1024)))

    import fitz
    import pytesseract
    from PIL import Image
    from .edit import parse_page_list

    _configure_pytesseract()
    lang = data.get('lang') or getattr(settings, 'OCR_LANG', 'eng')
    dpi = int(data.get('dpi') or OCR_DPI)
    want_txt = bool(data.get('txt'))

    _check_language_available(lang, tesseract_languages())

    pdf = fitz.open(file_path)
    output_path = create_output_path('.pdf', 'ocr_')
    txt_path = create_output_path('.txt', 'ocr_') if want_txt else None
    collected = []

    try:
        total = len(pdf)
        wanted = set()
        pages_str = (data.get('pages') or '').strip()
        if pages_str:
            wanted = set(parse_page_list(pages_str, total))

        # Enforce the page cap either way (explicit selection or whole file).
        # ``max_pages`` can be overridden by the caller (mainly for tests) but
        # may never exceed the hard cap.
        max_pages = min(int(data.get('max_pages') or OCR_MAX_PAGES),
                        OCR_MAX_PAGES)
        if len(wanted) > max_pages:
            raise OCRProcessingError(
                'You selected %d pages. OCR is limited to %d pages per run to '
                'protect server memory - please select fewer pages.'
                % (len(wanted), max_pages))
        if total > max_pages and not wanted:
            raise OCRProcessingError(
                'This PDF has %d pages. OCR is limited to %d pages per run. '
                'Please split the file or enter a page range such as 1-10.'
                % (total, max_pages))

        for i, page in enumerate(pdf):
            if wanted and (i + 1) not in wanted:
                continue
            image = None
            pix = None
            try:
                pix = page.get_pixmap(dpi=dpi)
                image = Image.open(io.BytesIO(pix.tobytes('png')))
                text = pytesseract.image_to_string(
                    image, lang=lang, timeout=OCR_PAGE_TIMEOUT)
            except pytesseract.TesseractNotFoundError:
                raise OCRNotConfiguredError(
                    'Tesseract was not found on this server, so OCR cannot run.')
            except pytesseract.TesseractError as exc:
                # Real Tesseract errors carry the useful reason; surface it.
                raw = str(exc) or ''
                if 'timeout' in raw.lower() or 'timed out' in raw.lower():
                    raise OCRProcessingError(
                        'Page %d took too long to process and was cancelled. '
                        'Try a clearer scan or fewer pages.' % (i + 1))
                detail = raw.strip().splitlines()
                detail = detail[-1] if detail else type(exc).__name__
                raise OCRProcessingError(
                    'Page %d could not be read: %s. If that mentions a language '
                    'file, the language pack is missing on the server.'
                    % (i + 1, detail))
            except subprocess.TimeoutExpired as exc:
                # pytesseract converts a kill into RuntimeError, but catch the
                # raw exception too in case a future version re-raises it.
                raise OCRProcessingError(
                    'Page %d took too long to process and was cancelled. Try a '
                    'clearer scan or fewer pages.' % (i + 1)) from exc
            except RuntimeError as exc:
                # pytesseract raises RuntimeError('Tesseract process timeout')
                # which is NOT a TesseractError, so without this branch a slow
                # page surfaced as the vague "OCR failed unexpectedly".
                if 'timeout' in str(exc).lower():
                    raise OCRProcessingError(
                        'Page %d took too long to process and was cancelled. '
                        'Try a clearer scan or fewer pages.' % (i + 1)) from exc
                raise
            finally:
                # Free the page image immediately, then shrink MuPDF's store.
                image = None
                pix = None
                fitz.TOOLS.store_shrink(100)

            if text and text.strip():
                collected.append(text)
                _write_invisible_layer(page, text, is_rtl=_has_arabic(text))

        pdf.save(output_path, garbage=3, deflate=True)
    except (OCRProcessingError, OCRNotConfiguredError):
        _cleanup([output_path, txt_path])
        raise
    except ValueError as exc:
        # Bad page range from parse_page_list: quote it verbatim, it is already
        # written for the user ("Invalid page number: 500").
        _cleanup([output_path, txt_path])
        raise OCRProcessingError(
            '%s This PDF has %d pages.' % (exc, len(pdf))) from exc
    except Exception as exc:
        _cleanup([output_path, txt_path])
        logger.exception('unexpected OCR failure on %s', file_path)
        if isinstance(exc, MemoryError) or 'memory' in str(exc).lower():
            raise OCRProcessingError(
                'The server ran out of memory processing this file. Please try '
                'a smaller file, or fewer pages at a time.')
        raise OCRProcessingError(
            'OCR failed unexpectedly. Please try a clearer scan or a smaller '
            'file.') from exc
    finally:
        pdf.close()

    if want_txt:
        with open(txt_path, 'w', encoding='utf-8') as fh:
            fh.write('\n\n'.join(collected).strip() + '\n')

    return output_path, txt_path