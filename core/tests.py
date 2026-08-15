from django.test import TestCase, Client
from django.urls import reverse

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