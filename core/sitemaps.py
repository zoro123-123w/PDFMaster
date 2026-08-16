from django.contrib.sitemaps import Sitemap
from django.urls import reverse


class StaticViewSitemap(Sitemap):
    priority = 0.8
    changefreq = 'weekly'

    def items(self):
        return [
            'home', 'tools_list', 'pricing', 'faq',
            'ai_tools', 'ai_study',
            'ai_summarize', 'ai_extract', 'ai_translate', 'ai_ask',
            'ai_study_quiz', 'ai_study_flashcards', 'ai_study_notes',
            'ai_study_guide', 'ai_study_questions', 'ai_study_important',
            'ai_study_chapters', 'ai_study_concepts', 'ai_study_exam',
            'merge_pdf', 'split_pdf', 'compress_pdf', 'jpg_to_pdf',
            'pdf_to_jpg', 'rotate_pdf', 'delete_pages', 'extract_pages',
            'pdf_to_word', 'pdf_to_excel', 'pdf_to_ppt', 'word_to_pdf',
            'excel_to_pdf', 'ppt_to_pdf', 'html_to_pdf', 'txt_to_pdf',
            'png_to_pdf', 'webp_to_pdf', 'pdf_to_png',
            'crop_pdf', 'watermark_pdf', 'add_page_numbers',
            'add_text_to_pdf', 'add_image_to_pdf', 'annotate_pdf',
            'highlight_pdf', 'redact_pdf', 'organize_pdf',
            'protect_pdf', 'unlock_pdf', 'sign_pdf',
            'repair_pdf', 'ocr_pdf', 'scan_to_pdf',
        ]

    def location(self, item):
        return reverse(item)