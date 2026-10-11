from django.conf import settings


def site_config(request):
    """Expose site-wide branding/SEO/ad settings to every template."""
    return {
        'SITE_URL': settings.SITE_URL,
        'ADSENSE_CLIENT_ID': getattr(settings, 'ADSENSE_CLIENT_ID', ''),
        'AD_SLOT_LEADERBOARD': getattr(settings, 'AD_SLOT_LEADERBOARD', ''),
        'AD_SLOT_INLINE': getattr(settings, 'AD_SLOT_INLINE', ''),
        'AD_GATE_ENABLED': getattr(settings, 'AD_GATE_ENABLED', False),
        'AD_GATE_URL': getattr(settings, 'AD_GATE_URL', ''),
        'AD_GATE_COOLDOWN_MIN': getattr(settings, 'AD_GATE_COOLDOWN_MIN', 10),
        'CSP_NONCE': getattr(request, 'csp_nonce', ''),
    }
