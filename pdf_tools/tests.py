from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from pypdf import PdfWriter
import io
import os

User = get_user_model()


def create_test_pdf(content="Test PDF content"):
    buffer = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.write(buffer)
    buffer.seek(0)
    return buffer


class PDFToolsURLTestCase(TestCase):
    """Test that every PDF tool URL returns 200 on GET."""

    def setUp(self):
        self.client = Client()

    def _test_get(self, url_name, args=None):
        url = reverse(url_name, args=args) if args else reverse(url_name)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200, f'{url_name} returned {response.status_code}')

    def test_tools_list(self):
        self._test_get('tools_list')

    def test_merge_pdf_get(self):
        self._test_get('merge_pdf')

    def test_split_pdf_get(self):
        self._test_get('split_pdf')

    def test_compress_pdf_get(self):
        self._test_get('compress_pdf')

    def test_jpg_to_pdf_get(self):
        self._test_get('jpg_to_pdf')

    def test_pdf_to_jpg_get(self):
        self._test_get('pdf_to_jpg')

    def test_rotate_pdf_get(self):
        self._test_get('rotate_pdf')

    def test_delete_pages_get(self):
        self._test_get('delete_pages')

    def test_extract_pages_get(self):
        self._test_get('extract_pages')

    def test_pdf_to_word_get(self):
        self._test_get('pdf_to_word')

    def test_pdf_to_excel_get(self):
        self._test_get('pdf_to_excel')

    def test_pdf_to_ppt_get(self):
        self._test_get('pdf_to_ppt')

    def test_word_to_pdf_get(self):
        self._test_get('word_to_pdf')

    def test_excel_to_pdf_get(self):
        self._test_get('excel_to_pdf')

    def test_ppt_to_pdf_get(self):
        self._test_get('ppt_to_pdf')

    def test_html_to_pdf_get(self):
        self._test_get('html_to_pdf')

    def test_txt_to_pdf_get(self):
        self._test_get('txt_to_pdf')

    def test_png_to_pdf_get(self):
        self._test_get('png_to_pdf')

    def test_webp_to_pdf_get(self):
        self._test_get('webp_to_pdf')

    def test_pdf_to_png_get(self):
        self._test_get('pdf_to_png')

    def test_crop_pdf_get(self):
        self._test_get('crop_pdf')

    def test_watermark_pdf_get(self):
        self._test_get('watermark_pdf')

    def test_add_page_numbers_get(self):
        self._test_get('add_page_numbers')

    def test_add_text_to_pdf_get(self):
        self._test_get('add_text_to_pdf')

    def test_add_image_to_pdf_get(self):
        self._test_get('add_image_to_pdf')

    def test_annotate_pdf_get(self):
        self._test_get('annotate_pdf')

    def test_highlight_pdf_get(self):
        self._test_get('highlight_pdf')

    def test_redact_pdf_get(self):
        self._test_get('redact_pdf')

    def test_organize_pdf_get(self):
        self._test_get('organize_pdf')

    def test_protect_pdf_get(self):
        self._test_get('protect_pdf')

    def test_unlock_pdf_get(self):
        self._test_get('unlock_pdf')

    def test_sign_pdf_get(self):
        self._test_get('sign_pdf')

    def test_repair_pdf_get(self):
        self._test_get('repair_pdf')

    def test_ocr_pdf_get(self):
        self._test_get('ocr_pdf')

    def test_scan_to_pdf_get(self):
        self._test_get('scan_to_pdf')

    def test_download_file(self):
        from pdf_tools.models import ProcessingJob
        job = ProcessingJob.objects.create(
            tool_name='test', original_filename='test.pdf',
            status='COMPLETED', output_file='',
        )
        response = self.client.get(reverse('download_file', args=[job.id]))
        self.assertEqual(response.status_code, 302)


class AIToolsURLTestCase(TestCase):

    def setUp(self):
        self.client = Client()

    def _test_get(self, url_name, args=None):
        url = reverse(url_name, args=args) if args else reverse(url_name)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200, f'{url_name} returned {response.status_code}')

    def test_ai_tools_list(self):
        self._test_get('ai_tools')

    def test_ai_summarize_get(self):
        self._test_get('ai_summarize')

    def test_ai_extract_get(self):
        self._test_get('ai_extract')

    def test_ai_translate_get(self):
        self._test_get('ai_translate')

    def test_ai_ask_get(self):
        self._test_get('ai_ask')

    def test_ai_study_list(self):
        self._test_get('ai_study')

    def test_ai_study_quiz_get(self):
        self._test_get('ai_study_quiz')

    def test_ai_study_flashcards_get(self):
        self._test_get('ai_study_flashcards')

    def test_ai_study_notes_get(self):
        self._test_get('ai_study_notes')

    def test_ai_study_guide_get(self):
        self._test_get('ai_study_guide')

    def test_ai_study_questions_get(self):
        self._test_get('ai_study_questions')

    def test_ai_study_important_get(self):
        self._test_get('ai_study_important')

    def test_ai_study_chapters_get(self):
        self._test_get('ai_study_chapters')

    def test_ai_study_concepts_get(self):
        self._test_get('ai_study_concepts')

    def test_ai_study_exam_get(self):
        self._test_get('ai_study_exam')


class PDFToolsWorkflowTestCase(TestCase):
    """Test actual PDF processing workflows."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='testpass123')

    def _make_pdf(self):
        buffer = io.BytesIO()
        writer = PdfWriter()
        writer.add_blank_page(width=200, height=200)
        writer.add_blank_page(width=200, height=200)
        writer.write(buffer)
        buffer.seek(0)
        return SimpleUploadedFile('test.pdf', buffer.read(), content_type='application/pdf')

    def test_merge_pdf_post(self):
        pdf1 = self._make_pdf()
        pdf2 = self._make_pdf()
        response = self.client.post(reverse('merge_pdf'), {
            'files': [pdf1, pdf2]
        })
        self.assertIn(response.status_code, [200, 302])

    def test_compress_pdf_post(self):
        pdf = self._make_pdf()
        response = self.client.post(reverse('compress_pdf'), {'file': pdf})
        self.assertEqual(response.status_code, 200)

    def test_split_pdf_post(self):
        pdf = self._make_pdf()
        response = self.client.post(reverse('split_pdf'), {
            'file': pdf, 'pages': '1'
        })
        self.assertIn(response.status_code, [200, 302])

    def test_rotate_pdf_post(self):
        pdf = self._make_pdf()
        response = self.client.post(reverse('rotate_pdf'), {
            'file': pdf, 'angle': '90'
        })
        self.assertIn(response.status_code, [200, 302])

    def test_delete_pages_post(self):
        pdf = self._make_pdf()
        response = self.client.post(reverse('delete_pages'), {
            'file': pdf, 'pages': '1'
        })
        self.assertIn(response.status_code, [200, 302])

    def test_extract_pages_post(self):
        pdf = self._make_pdf()
        response = self.client.post(reverse('extract_pages'), {
            'file': pdf, 'pages': '1'
        })
        self.assertIn(response.status_code, [200, 302])

    def test_organize_pdf_post(self):
        pdf = self._make_pdf()
        response = self.client.post(reverse('organize_pdf'), {
            'file': pdf, 'order': '2,1', 'rotation': '0'
        })
        self.assertIn(response.status_code, [200, 302])

    def test_crop_pdf_post(self):
        pdf = self._make_pdf()
        response = self.client.post(reverse('crop_pdf'), {
            'file': pdf, 'left': '10', 'right': '10', 'top': '10', 'bottom': '10', 'pages': ''
        })
        self.assertIn(response.status_code, [200, 302])

    def test_watermark_pdf_post(self):
        pdf = self._make_pdf()
        response = self.client.post(reverse('watermark_pdf'), {
            'file': pdf, 'text': 'CONFIDENTIAL', 'position': 'center',
            'opacity': '0.3', 'fontsize': '30', 'pages': ''
        })
        self.assertIn(response.status_code, [200, 302])

    def test_protect_pdf_post(self):
        pdf = self._make_pdf()
        response = self.client.post(reverse('protect_pdf'), {
            'file': pdf, 'password': 'secret123', 'confirm_password': 'secret123'
        })
        self.assertIn(response.status_code, [200, 302])

    def test_add_page_numbers_post(self):
        pdf = self._make_pdf()
        response = self.client.post(reverse('add_page_numbers'), {
            'file': pdf, 'position': 'bottom-center', 'start': '1', 'fontsize': '14'
        })
        self.assertIn(response.status_code, [200, 302])

    def test_repair_pdf_post(self):
        pdf = self._make_pdf()
        response = self.client.post(reverse('repair_pdf'), {'file': pdf})
        self.assertIn(response.status_code, [200, 302])
