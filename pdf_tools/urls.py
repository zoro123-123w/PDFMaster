from django.urls import path
from . import views

urlpatterns = [
    path('', views.tools_list, name='tools_list'),

    # --- Existing 8 tools ---
    path('merge-pdf/', views.merge_pdf, name='merge_pdf'),
    path('split-pdf/', views.split_pdf, name='split_pdf'),
    path('compress-pdf/', views.compress_pdf, name='compress_pdf'),
    path('jpg-to-pdf/', views.jpg_to_pdf, name='jpg_to_pdf'),
    path('pdf-to-jpg/', views.pdf_to_jpg, name='pdf_to_jpg'),
    path('rotate-pdf/', views.rotate_pdf, name='rotate_pdf'),
    path('delete-pages/', views.delete_pages, name='delete_pages'),
    path('extract-pages/', views.extract_pages, name='extract_pages'),

    # --- PDF Convert ---
    path('pdf-to-word/', views.pdf_to_word, name='pdf_to_word'),
    path('pdf-to-excel/', views.pdf_to_excel, name='pdf_to_excel'),
    path('pdf-to-ppt/', views.pdf_to_ppt, name='pdf_to_ppt'),
    path('word-to-pdf/', views.word_to_pdf, name='word_to_pdf'),
    path('excel-to-pdf/', views.excel_to_pdf, name='excel_to_pdf'),
    path('ppt-to-pdf/', views.ppt_to_pdf, name='ppt_to_pdf'),
    path('html-to-pdf/', views.html_to_pdf, name='html_to_pdf'),
    path('txt-to-pdf/', views.txt_to_pdf, name='txt_to_pdf'),
    path('png-to-pdf/', views.png_to_pdf, name='png_to_pdf'),
    path('webp-to-pdf/', views.webp_to_pdf, name='webp_to_pdf'),
    path('pdf-to-png/', views.pdf_to_png, name='pdf_to_png'),

    # --- PDF Edit ---
    path('crop-pdf/', views.crop_pdf, name='crop_pdf'),
    path('watermark-pdf/', views.watermark_pdf, name='watermark_pdf'),
    path('page-numbers/', views.add_page_numbers, name='add_page_numbers'),
    path('add-text/', views.add_text_to_pdf, name='add_text_to_pdf'),
    path('add-image/', views.add_image_to_pdf, name='add_image_to_pdf'),
    path('annotate/', views.annotate_pdf, name='annotate_pdf'),
    path('highlight/', views.highlight_pdf, name='highlight_pdf'),
    path('redact/', views.redact_pdf, name='redact_pdf'),

    # --- PDF Organize ---
    path('organize/', views.organize_pdf, name='organize_pdf'),

    # --- PDF Security ---
    path('protect/', views.protect_pdf, name='protect_pdf'),
    path('unlock/', views.unlock_pdf, name='unlock_pdf'),
    path('sign/', views.sign_pdf_view, name='sign_pdf'),

    # --- PDF Optimize ---
    path('repair/', views.repair_pdf, name='repair_pdf'),

    # --- PDF OCR ---
    path('ocr/', views.ocr_pdf_view, name='ocr_pdf'),
    path('scan-to-pdf/', views.scan_to_pdf, name='scan_to_pdf'),

    path('download/<uuid:job_id>/', views.download_file, name='download_file'),
]
