# PDF Master - production image.
#
# The whole point of this Dockerfile is that OCR works out of the box. A bare
# python:3.11-slim image has NO Tesseract, so every OCR request died with
# "OCR is not configured on this server". The apt packages below are mandatory,
# not optional:
#   tesseract-ocr-all      the engine PLUS every language pack (~130 langs), so
#                          the language dropdown can be built from --list-langs
#   poppler-utils          pdftoppm/pdfinfo for PDF rasterisation fallbacks
#   ghostscript            PDF compression / repair helpers used by other tools
#   fonts-noto-core        Latin glyphs
#   fonts-noto-core-extra  Greek / Cyrillic / Hebrew for the text layer
#   fonts-noto-extra       Devanagari, CJK, Khmer ... (the non-Latin packs)
#   fonts-noto-naskh-arabic / amiri   Arabic-script (Urdu, Farsi) glyphs
#
# SIZE / BUILD WARNING (see DEPLOY.md):
#   tesseract-ocr-all pulls ~130 `tesseract-ocr-<lang>` packages. Measured on
#   Debian bookworm this adds roughly 1.3 GB of installed packages, giving a
#   total image of about 1.5 GB, and `apt-get` install dominates the build
#   (expect ~5-10 minutes longer than the two-pack version).
#
#   It does NOT change runtime RAM. Tesseract's memory use is driven by the
#   render DPI and the page's pixel count, not by how many packs are on disk.
#   A pack's .traineddata is memory-mapped per request only for the languages
#   actually selected (and OCR is capped at 2 languages). So a 512 MB instance
#   is still fine at 200 DPI, page by page - see OCR_DPI / OCR_MAX_PAGES.
#   The cost is disk and build time, not memory.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    TESSERACT_CMD=/usr/bin/tesseract \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

# libgl1/libglib2.0-0 are needed by Pillow's wheel; fonts are needed so the
# invisible OCR text layer can actually represent non-Latin scripts.
RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-all \
        poppler-utils \
        ghostscript \
        fonts-noto-core \
        fonts-noto-core-extra \
        fonts-noto-extra \
        fonts-noto-naskh-arabic \
        fonts-amiri \
        fonts-dejavu-core \
        libgl1 \
        libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Fail the BUILD loudly if Tesseract or the language packs are missing, instead
# of shipping an image where the dropdown looks full but OCR silently fails.
# tesseract-ocr-all should report well over 100 languages; require a healthy
# number so a trimmed/failed install can never pass unnoticed.
RUN tesseract --version \
    && LANGS="$(tesseract --list-langs 2>/dev/null | grep -c '^[a-z][a-z]*$')" \
    && echo "tesseract languages installed: ${LANGS}" \
    && test "${LANGS}" -ge 100 \
    && tesseract --list-langs 2>/dev/null | grep -q '^eng$' \
    && tesseract --list-langs 2>/dev/null | grep -q '^urd$' \
    && echo "Tesseract OK: engine + ${LANGS} language packs verified"

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# collectstatic needs SECRET_KEY to be set; a throwaway value is fine because it
# is only used to hash manifest file names at build time.
RUN SECRET_KEY=build-only-secret python manage.py collectstatic --noinput

# SQLite lives on the container filesystem, so migrations must run at STARTUP,
# not at build time (the built image is immutable and Render may redeploy it).
ENV PORT=10000 \
    WEB_CONCURRENCY=2

EXPOSE 10000

CMD ["sh", "-c", "python manage.py migrate --noinput && \
    gunicorn config.wsgi:application \
    --bind 0.0.0.0:${PORT} \
    --workers ${WEB_CONCURRENCY} \
    --timeout 120 \
    --graceful-timeout 30 \
    --access-file -"]
