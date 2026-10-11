"""Content-Security-Policy middleware.

Builds a per-request CSP header with a fresh nonce that templates use on
their inline <script> blocks (exposed as ``CSP_NONCE`` by the site_config
context processor). Ad-related origins are added to script/img/connect/frame
sources ONLY when an AdSense client is configured - when ads are off the
policy stays strict. ``CSP_ENABLED=False`` skips the header entirely
(debugging escape hatch; default on).

``script-src-attr 'unsafe-inline'`` keeps the existing inline event handlers
(``onclick`` etc.) working: nonced ``script-src`` alone blocks them, and CSP3
allows the attribute sink to be relaxed independently of the script sink.
``style-src 'unsafe-inline'`` covers inline ``style=`` attributes and
``<style>`` blocks used by tool pages.
"""

import secrets

from django.conf import settings

# Origins needed by AdSense creatives; only added when ads are enabled.
_AD_SCRIPT_SRC = [
    'https://pagead2.googlesyndication.com',
    'https://googleads.g.doubleclick.net',
]
_AD_IMG_SRC = [
    'https://pagead2.googlesyndication.com',
    'https://googleads.g.doubleclick.net',
    'https://tpc.googlesyndication.com',
    'https://www.google.com',
]
_AD_FRAME_SRC = [
    'https://googleads.g.doubleclick.net',
    'https://tpc.googlesyndication.com',
]


class ContentSecurityPolicyMiddleware:
    """Attach a Content-Security-Policy header to HTML responses."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.enabled = getattr(settings, 'CSP_ENABLED', True)

    def __call__(self, request):
        nonce = secrets.token_urlsafe(16)
        # Context processors read the nonce from the request while rendering.
        request.csp_nonce = nonce
        response = self.get_response(request)
        if self.enabled and self._is_html(response):
            response['Content-Security-Policy'] = self._policy(nonce)
        return response

    @staticmethod
    def _is_html(response):
        content_type = response.get('Content-Type', '') or ''
        return content_type.startswith('text/html')

    def _policy(self, nonce):
        ads_on = bool(getattr(settings, 'ADSENSE_CLIENT_ID', ''))
        script_src = ["'self'", f"'nonce-{nonce}'"]
        img_src = ["'self'", 'data:', 'blob:']
        connect_src = ["'self'"]
        frame_src = ["'self'"]
        if ads_on:
            script_src += _AD_SCRIPT_SRC
            img_src += _AD_IMG_SRC
            connect_src += _AD_SCRIPT_SRC
            frame_src += _AD_FRAME_SRC
        directives = [
            "default-src 'self'",
            'script-src ' + ' '.join(script_src),
            "script-src-attr 'unsafe-inline'",
            "style-src 'self' 'unsafe-inline'",
            'img-src ' + ' '.join(img_src),
            "font-src 'self' data:",
            'connect-src ' + ' '.join(connect_src),
            'frame-src ' + ' '.join(frame_src),
            "object-src 'none'",
            "base-uri 'self'",
            "form-action 'self'",
            "frame-ancestors 'none'",
        ]
        return '; '.join(directives)