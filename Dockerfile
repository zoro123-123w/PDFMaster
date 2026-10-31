FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    TESSERACT_CMD=/usr/bin/tesseract \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PORT=7860 \
    WEB_CONCURRENCY=2

# Install system dependencies needed by the project
RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-eng \
        tesseract-ocr-urd \
        poppler-utils \
        ghostscript \
        libmagic1 \
        libjpeg-dev \
        zlib1g-dev \
        libpng-dev \
        fonts-noto-core \
        fonts-noto-core-extra \
        fonts-noto-extra \
        fonts-noto-naskh-arabic \
        fonts-amiri \
        fonts-dejavu-core \
        libgl1 \
        libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Verify Tesseract installation
RUN tesseract --version \
    && LANGS="$(tesseract --list-langs 2>/dev/null | grep -c '^[a-z][a-z]*$')" \
    && echo "tesseract languages installed: ${LANGS}" \
    && test "${LANGS}" -ge 2 \
    && tesseract --list-langs 2>/dev/null | grep -q '^eng$' \
    && tesseract --list-langs 2>/dev/null | grep -q '^urd$' \
    && echo "Tesseract OK: engine + ${LANGS} language packs verified"

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create non-root user with UID 1000 and set ownership
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Collect static files during build
RUN SECRET_KEY=build-only-secret python manage.py collectstatic --noinput

EXPOSE 7860

# Run migrations and start gunicorn bound to 0.0.0.0:7860
CMD ["sh", "-c", "python manage.py migrate --noinput && gunicorn config.wsgi:application --bind 0.0.0.0:7860 --workers ${WEB_CONCURRENCY} --timeout 120"]
