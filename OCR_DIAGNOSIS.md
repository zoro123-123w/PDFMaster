# OCR failure - root cause analysis

## 1. What actually broke

**Local (immediate blocker): the virtualenv was corrupt.**
`venv/pyvenv.cfg` pointed at `C:\Users\Ali\AppData\Local\Programs\Python\Python313\python.exe`,
a path that does not exist, so *every* `venv\Scripts\python.exe` call died with
"did not find executable at ...". On top of that `pytesseract` was not
installed. Fixed by repointing `pyvenv.cfg` at the working embeddable
`C:\Python313Embed\python.exe` (3.13.6) and reinstalling requirements.

**Two real bugs remain in `pdf_tools/services/ocr.py` that break OCR on the
server even when Tesseract IS installed.** Both proven with `diag_ocr.py`:

### BUG 1 - the configured Tesseract path is thrown away
```
settings.TESSERACT_CMD               = ''
after setting TESSERACT_CMD=/nonexistent/tesseract
  _resolve_tesseract_cmd() -> C:\Program Files\Tesseract-OCR\tesseract.exe
  tesseract_available()    -> True
  pytesseract still uses   -> 'tesseract'
```
`_resolve_tesseract_cmd()` computes a path but never assigns it to
`pytesseract.pytesseract.tesseract_cmd`. pytesseract therefore always shells out
to bare `tesseract` and relies purely on `PATH`. On Render the binary is at
`/usr/bin/tesseract`, which is normally on PATH, but the moment anyone sets
`TESSERACT_CMD` (exactly what you do when the default detection is wrong) it is
silently ignored - while `tesseract_available()` still reports `True`, so the UI
never warns you.

### BUG 2 - real Tesseract errors are swallowed
```
a) raw error type   : TesseractError
   raw error message: Error opening data file .../tessdata/zzz_not_a_lang.traineddata
                      Please make sure that the TESSDATA_PREFIX environment variable
                      is set ... Could not initialize tesseract.
b) user-visible error: OCR failed on page 1: TesseractError
```
The broad `except Exception` wrapper turns *every* failure - missing language
pack, wrong lang code, out-of-memory, timeout - into
`OCR failed on page N: TesseractError`, with nothing written to the log. That is
why "OCR is not working" gave no actionable message.

### BUG 3 - the searchable layer can be silently dropped
```
insert_textbox into a full page -> return value -260.75, text NOT written
```
`insert_textbox()` returns a negative number when the text does not fit and then
writes **nothing**. A dense scanned page loses its entire invisible text layer
and the output "succeeds" as an image-only PDF again. A line-by-line writer
(`insert_text` / `TextWriter`) cannot overflow silently.

### BUG 4 - memory grows without bound (512 MB risk)
Measured with `mem_ocr.py`, 10 pages at 200 DPI:
```
start peak RSS: 68 MB -> after page 10: 160 MB  (growth ~91 MB / 10 pages)
```
PyMuPDF's render cache is never released. At 30 pages this is ~300 MB before
Gunicorn's own footprint, which is exactly the OOM kill on a 512 MB instance.
Fixed with `pymupdf.TOOLS.store_shrink(100)` per page plus explicit
`pix = None`.

### BUG 5 - Urdu in the searchable layer
`helv` (base-14) has no Arabic glyphs, so Urdu output became mojibake:
```
helv  -> 'no Arabic glyphs'
```
`pymupdf-fonts` ships no Arabic face either, so the fix embeds
`NotoNaskhArabic-Regular.ttf` (installed on Debian via
`fonts-noto-core fonts-noto-naskh-arabic`) and falls back to `helv` for Latin.

## 2. Known limitation, not silently hidden
Shaping means extracted Urdu comes back as **presentation forms**
(`\uFEE5`) rather than base letters (`\u067E`), so a viewer "find" on a base
codepoint can miss. Verified at codepoint level with `test_idh.py` /
`codepoint_report.txt`. The words are all present and correct in reading order -
this is a rendering artefact of shaped Arabic, and the honest fix is to tell the
user that the `.txt` export is the reliable way to reuse Urdu text.

## 3. Timing (10 pages, 200 DPI, eng)
```
10 pages @200dpi took 11.0s, chars=1341   peak RSS 160 MB before the fix
```

## 4. Dockerfile requirement
`tesseract-ocr tesseract-ocr-all poppler-utils ghostscript`
plus the Noto Arabic fonts. `poppler-utils`/`ghostscript` are not used by the
current PyMuPDF pipeline but are installed because the user asked for them and
they are the standard companions for server-side PDF work.

## 5. Multi-language support (all Tesseract languages)

The dropdown is not hardcoded. It is built at runtime from
`tesseract --list-langs`, so it always matches what the image actually has.

* `Dockerfile` installs `tesseract-ocr-all` (~130 packs), not just eng/urd.
* Two dropdowns: primary language + optional second language (`lang`, `lang2`).
  `services.ocr.normalize_langs()` joins them into Tesseract's `"eng+urd"` form,
  dropping blanks and duplicates.
* Max 2 packs per run (`OCR_MAX_LANGS`). The service raises a clear error for 3+.
* Codes are validated against the real installed list, so an uninstalled pack can
  never be submitted - the user gets "The 'zz_nope' language pack is not
  installed on this server" instead of an opaque TesseractError.
* The dropdown has a type-to-filter search box, because ~130 raw options in a
  plain `<select>` is unusable.

### Size / build cost of `tesseract-ocr-all`

* ~1.3 GB of installed apt packages, ~1.5 GB total image (vs ~450 MB for eng+urd
  only). Build time is dominated by `apt-get`: budget roughly 4-8 minutes.
* RAM: the packs live on **disk**, not in memory. Only the 1-2 packs you select
  are loaded, and only one page is resident at a time (~9 MB at 200 DPI).
  Measured peak stayed ~160 MB for a 10-page run, so this still fits a 512 MB
  instance.
* The larger image means slower cold starts and slower deploys. If disk space
  ever becomes a problem, swap `tesseract-ocr-all` for the specific
  `tesseract-ocr-<lang>` packages you need; the dropdown adapts automatically.

## 6. How to re-run the checks

```powershell
python -m scripts.smoke_ocr                          # 6 end-to-end checks
python -m scripts.verify_ocr                         # 10 cases
python manage.py test tests pdf_tools.tests          # 81 tests
```

`scripts/check_urdu_txt.py` proves the Urdu TXT download is real UTF-8 by
comparing code points (the Windows console cannot render Arabic, so eyeballing
the terminal proves nothing).
