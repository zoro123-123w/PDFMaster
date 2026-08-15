from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
import io
from pypdf import PdfWriter

User = get_user_model()

def create_test_pdf(content="Test PDF"):
    buffer = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.write(buffer)
    buffer.seek(0)
    return buffer

class PDFToolsTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='testpass123')

    def test_tools_page(self):
        response = self.client.get(reverse('tools_list'))
        self.assertEqual(response.status_code, 200)

    def test_merge_pdf_get(self):
        response = self.client.get(reverse('merge_pdf'))
        self.assertEqual(response.status_code, 200)

    def test_merge_pdf_post(self):
        pdf1 = create_test_pdf()
        pdf2 = create_test_pdf()
        response = self.client.post(reverse('merge_pdf'), {
            'files': [pdf1, pdf2]
        })
        self.assertIn(response.status_code, [200, 302])

    def test_split_pdf_get(self):
        response = self.client.get(reverse('split_pdf'))
        self.assertEqual(response.status_code, 200)

    def test_compress_pdf_get(self):
        response = self.client.get(reverse('compress_pdf'))
        self.assertEqual(response.status_code, 200)

    def test_jpg_to_pdf_get(self):
        response = self.client.get(reverse('jpg_to_pdf'))
        self.assertEqual(response.status_code, 200)

    def test_pdf_to_jpg_get(self):
        response = self.client.get(reverse('pdf_to_jpg'))
        self.assertEqual(response.status_code, 200)

    def test_rotate_pdf_get(self):
        response = self.client.get(reverse('rotate_pdf'))
        self.assertEqual(response.status_code, 200)

    def test_delete_pages_get(self):
        response = self.client.get(reverse('delete_pages'))
        self.assertEqual(response.status_code, 200)

    def test_extract_pages_get(self):
        response = self.client.get(reverse('extract_pages'))
        self.assertEqual(response.status_code, 200)

    def test_dashboard_requires_login(self):
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 302)

    def test_dashboard_with_login(self):
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)