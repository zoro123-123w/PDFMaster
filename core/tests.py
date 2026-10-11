from django.conf import settings
from django.test import TestCase, Client
from django.urls import reverse
from django.test import override_settings

class CoreViewsTestCase(TestCase):
    def setUp(self):
        self.client = Client()

    def test_home_page(self):
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)

    def test_pricing_page(self):
        response = self.client.get(reverse('pricing'))
        self.assertEqual(response.status_code, 200)

    def test_faq_page(self):
        response = self.client.get(reverse('faq'))
        self.assertEqual(response.status_code, 200)

    def test_dashboard_requires_login(self):
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 302)

    def test_robots_txt(self):
        response = self.client.get('/robots.txt')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/plain')
        content = response.content.decode()
        self.assertIn('Allow: /', content)
        self.assertIn('Sitemap:', content)
        # Critical: must NOT block the entire site
        for line in content.splitlines():
            self.assertNotEqual(line.strip(), 'Disallow: /')

    def test_robots_txt_no_global_disallow(self):
        """Critical: robots.txt must NOT block the entire site."""
        response = self.client.get('/robots.txt')
        content = response.content.decode()
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith('Disallow:'):
                self.assertNotEqual(stripped, 'Disallow: /',
                    'Found global Disallow: / which blocks the entire site')

    @override_settings(ALLOWED_HOSTS=['*'], SITE_URL='https://example.com')
    def test_robots_txt_contains_sitemap(self):
        """Sitemap URL must come from SITE_URL and use HTTPS."""
        response = self.client.get('/robots.txt', HTTP_HOST='example.com')
        content = response.content.decode()
        self.assertIn('Sitemap: https://example.com/sitemap.xml', content)

    def test_robots_txt_sitemap_ignores_spoofed_host(self):
        """The Sitemap line must be built from SITE_URL, not the Host header."""
        with self.settings(ALLOWED_HOSTS=['*']):
            response = self.client.get('/robots.txt', HTTP_HOST='evil.example')
        content = response.content.decode()
        self.assertIn(
            f'Sitemap: {settings.SITE_URL}/sitemap.xml', content)
        self.assertNotIn('evil.example', content)

    def test_robots_txt_disallows_download_paths(self):
        response = self.client.get('/robots.txt')
        content = response.content.decode()
        self.assertIn('Disallow: /download/', content)
        self.assertIn('Disallow: /tools/download/', content)

    @override_settings(ALLOWED_HOSTS=['*'])
    def test_robots_txt_production_sitemap(self):
        """Verify sitemap URL matches production domain and uses HTTPS."""
        response = self.client.get(
            '/robots.txt',
            HTTP_HOST='pdfmaster-s29m.onrender.com',
            HTTP_X_FORWARDED_PROTO='https',
        )
        content = response.content.decode()
        self.assertIn('https://pdfmaster-s29m.onrender.com/sitemap.xml', content)