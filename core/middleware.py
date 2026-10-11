"""Lightweight security middleware for PDFMaster.

Rate limiting: throttles POST requests to tool endpoints per client IP using
the Django cache framework (no external dependency). Limits are enforced with
a fixed-window counter and are intended as a first line of defence against
abuse, not as a hard security boundary - in production put a CDN/WAF (e.g.
Cloudflare) in front as well.

Temp file cleanup: ``cleanup_temp_files()`` deletes stale files under
MEDIA_ROOT/temp. It is called from the cleanup management command and can be
invoked from a cron job or Render's scheduled jobs.
"""
import os
import time

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse

# POST paths that trigger file processing. Everything under these prefixes is
# throttled; GET requests are never limited.
THROTTLED_PREFIXES = ('/tools/', '/ai-tools/')

# Defaults (overridable via settings / env).
RATE_LIMIT_WINDOW_SECONDS = 3600          # one hour fixed window
RATE_LIMIT_MAX_POSTS = 60                 # POSTs per window per IP
RATE_LIMIT_MAX_UPLOADS = 20               # larger POSTs (with a file body) per window


class RateLimitMiddleware:
    """Fixed-window per-IP rate limit for tool POSTs."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.enabled = getattr(settings, 'RATE_LIMIT_ENABLED', True)
        self.window = getattr(settings, 'RATE_LIMIT_WINDOW_SECONDS', RATE_LIMIT_WINDOW_SECONDS)
        self.max_posts = getattr(settings, 'RATE_LIMIT_MAX_POSTS', RATE_LIMIT_MAX_POSTS)
        self.max_uploads = getattr(settings, 'RATE_LIMIT_MAX_UPLOADS', RATE_LIMIT_MAX_UPLOADS)

    def __call__(self, request):
        if self.enabled and request.method == 'POST' and self._throttled(request):
            return HttpResponse(
                'Too many requests. Please wait a moment and try again.',
                status=429,
                content_type='text/plain',
            )
        return self.get_response(request)

    # --- internals ----------------------------------------------------- #
    def _client_ip(self, request):
        xff = request.META.get('HTTP_X_FORWARDED_FOR')
        if xff:
            return xff.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', 'unknown')

    def _over_limit(self, key, limit):
        """Increment the counter for ``key`` and return True when over limit."""
        cache_key = f'ratelimit:{key}:{int(time.time() // self.window)}'
        try:
            count = cache.incr(cache_key)
        except ValueError:
            # Key expired or never set: start a new window.
            cache.set(cache_key, 1, self.window)
            count = 1
        return count > limit

    def _throttled(self, request):
        path = request.path
        if not path.startswith(THROTTLED_PREFIXES):
            return False
        ip = self._client_ip(request)
        # Treat requests that carry a file upload (multipart with CONTENT_LENGTH
        # above a small threshold) as "uploads" with a tighter budget.
        try:
            content_length = int(request.META.get('CONTENT_LENGTH') or 0)
        except (TypeError, ValueError):
            content_length = 0
        if content_length > 10 * 1024:  # > 10 KB body -> assume a file upload
            return self._over_limit(f'{ip}:upload', self.max_uploads)
        return self._over_limit(f'{ip}:post', self.max_posts)


# --- Temp file cleanup -------------------------------------------------- #
def cleanup_temp_files(max_age_hours=None):
    """Delete files under MEDIA_ROOT/temp older than ``max_age_hours``.

    Defaults to settings.TEMP_FILE_MAX_AGE_HOURS (or 6). Returns the number of
    files removed. Safe to call repeatedly; used by the ``cleanup_temp``
    management command and by cron/Render scheduled jobs.
    """
    from django.conf import settings as _s
    if max_age_hours is None:
        max_age_hours = getattr(_s, 'TEMP_FILE_MAX_AGE_HOURS', 6)
    temp_dir = os.path.join(_s.MEDIA_ROOT, 'temp')
    if not os.path.isdir(temp_dir):
        return 0
    cutoff = time.time() - max_age_hours * 3600
    removed = 0
    for root, _dirs, files in os.walk(temp_dir):
        for name in files:
            path = os.path.join(root, name)
            try:
                if os.path.getmtime(path) < cutoff:
                    os.remove(path)
                    removed += 1
            except OSError:
                # File was removed concurrently or is unreadable - skip.
                continue
    return removed
