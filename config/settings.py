import os
import sys

import dj_database_url

from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-change-me-in-production')

DEBUG = os.environ.get('DEBUG', 'False').lower() in ('1', 'true', 'yes')

ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1,.hf.space').split(',')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sitemaps',
    'core',
    'pdf_tools',
    'ai_tools',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'core.middleware.RateLimitMiddleware',
    'core.csp.ContentSecurityPolicyMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'core.context_processors.site_config',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL:
    DATABASES = {
        'default': dj_database_url.parse(DATABASE_URL, conn_max_age=600, ssl_require=True)
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': os.environ.get('SQLITE_PATH') or str(BASE_DIR / 'db.sqlite3'),
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

CSRF_TRUSTED_ORIGINS = ['https://*.hf.space']
if os.environ.get('CSRF_TRUSTED_ORIGINS'):
    CSRF_TRUSTED_ORIGINS += os.environ.get('CSRF_TRUSTED_ORIGINS').split(',')

X_FRAME_OPTIONS = 'DENY'

# Trust X-Forwarded-Proto from proxies/load balancers so
# request.is_secure() and build_absolute_uri() use HTTPS in production.
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Use /tmp for media on ephemeral filesystems (Hugging Face Spaces)
MEDIA_URL = 'media/'
MEDIA_ROOT = os.environ.get('MEDIA_ROOT') or '/tmp/media'

# Ensure media directories exist
os.makedirs(os.path.join(MEDIA_ROOT, 'temp'), exist_ok=True)

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# AI Integration (optional - for AI-powered PDF features)
# Configuration is read from environment variables only; API keys are never hardcoded.
AI_API_KEY = os.getenv('AI_API_KEY', '')
AI_PROVIDER = os.getenv('AI_PROVIDER', 'groq')
AI_DEFAULT_MODEL = os.getenv('AI_DEFAULT_MODEL', 'openai/gpt-oss-120b')
AI_BASE_URL = os.getenv('AI_BASE_URL', 'https://api.groq.com/openai/v1')
AI_TIMEOUT_SECONDS = float(os.getenv('AI_TIMEOUT_SECONDS', '30'))

# OCR (Tesseract) - optional system dependency.
# Leave TESSERACT_CMD empty to rely on the binary being on PATH (the normal case
# in the Docker image). Set it only if Tesseract lives somewhere unusual.
TESSERACT_CMD = os.getenv('TESSERACT_CMD', '')

# OCR limits. The server may have only 512 MB, so these caps keep a single
# request from exhausting it: 20 MB, 30 pages, 200 DPI, 60s per page.
OCR_MAX_PAGES = int(os.getenv('OCR_MAX_PAGES', '30'))
OCR_MAX_FILE_SIZE = int(os.getenv('OCR_MAX_FILE_SIZE', 20 * 1024 * 1024))
OCR_DPI = int(os.getenv('OCR_DPI', '200'))
OCR_PAGE_TIMEOUT = int(os.getenv('OCR_PAGE_TIMEOUT', '60'))

MAX_UPLOAD_SIZE = int(os.getenv('MAX_UPLOAD_SIZE', 26214400))

# Canonical site origin used for canonical/OG URLs, sitemap and JSON-LD.
# Falls back to the production Render domain, then to a local origin.
SITE_URL = os.getenv('SITE_URL', 'https://pdfmaster-s29m.onrender.com').rstrip('/')

# Ads (optional). Leave ADSENSE_CLIENT_ID empty to render no ad slots at all.
ADSENSE_CLIENT_ID = os.getenv('ADSENSE_CLIENT_ID', '')
# AdSense slot IDs for the built-in banner positions.
AD_SLOT_LEADERBOARD = os.getenv('AD_SLOT_LEADERBOARD', '')
AD_SLOT_INLINE = os.getenv('AD_SLOT_INLINE', '')

# Ad-gate (optional interstitial). When enabled AND a URL is set, the first
# "Download" or "Start OCR" click inside a tab opens the ad in a new tab
# (window.open with noopener) and the original action still runs on the same
# page - the current page is never redirected. Clicks inside one tab are
# suppressed for AD_GATE_COOLDOWN_MIN minutes (sessionStorage). Rendered and
# loaded as a no-op when disabled or when the URL is empty.
AD_GATE_ENABLED = os.getenv('AD_GATE_ENABLED', 'False').lower() in ('1', 'true', 'yes')
AD_GATE_URL = os.getenv('AD_GATE_URL', '')
AD_GATE_COOLDOWN_MIN = int(os.getenv('AD_GATE_COOLDOWN_MIN', '10'))

# Content-Security-Policy (core/csp.py). Nonce-based for inline scripts;
# ad origins are added only when ADSENSE_CLIENT_ID is set. Disable for
# local debugging only - do not ship with CSP off.
CSP_ENABLED = os.getenv('CSP_ENABLED', 'True').lower() not in ('0', 'false', 'no')

# --- Security -----------------------------------------------------------
# Per-IP rate limit for tool POSTs (see core/middleware.py).
# Disabled automatically while running the test suite so tests don't trip it.
TESTING = 'test' in sys.argv
RATE_LIMIT_ENABLED = (
    not TESTING
    and os.getenv('RATE_LIMIT_ENABLED', 'True').lower() not in ('0', 'false', 'no')
)
RATE_LIMIT_WINDOW_SECONDS = int(os.getenv('RATE_LIMIT_WINDOW_SECONDS', '3600'))
RATE_LIMIT_MAX_POSTS = int(os.getenv('RATE_LIMIT_MAX_POSTS', '60'))
RATE_LIMIT_MAX_UPLOADS = int(os.getenv('RATE_LIMIT_MAX_UPLOADS', '20'))

# Cache used by the rate limiter (and anything else on django.core.cache).
# Set REDIS_URL to use a SHARED cache - strongly recommended in production:
# without it the LocMemCache default is per-process, so with N gunicorn
# workers each client effectively gets N x the configured limit. Django's
# built-in RedisCache backend needs the `redis` package (see requirements).
REDIS_URL = os.getenv('REDIS_URL', '').strip()
if REDIS_URL:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': REDIS_URL,
        }
    }
else:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'pdfmaster-ratelimit',
        }
    }
# Files in MEDIA_ROOT/temp older than this many hours are deleted by
# `manage.py cleanup_temp` (run via cron / Render scheduled job).
TEMP_FILE_MAX_AGE_HOURS = int(os.getenv('TEMP_FILE_MAX_AGE_HOURS', '6'))

LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'dashboard'
LOGOUT_REDIRECT_URL = 'home'

STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'},
}
