# PDFMaster

All Your PDF Tools in One Place

A professional Django-based web application providing PDF processing tools, AI PDF tools, and an AI Study suite — all in one platform.

## Features

### PDF Toolkit (8+ core tools)
- **Merge PDF** — Combine multiple PDFs into one
- **Split PDF** — Split by page ranges
- **Compress PDF** — Reduce file size with configurable compression levels
- **JPG/PNG to PDF** — Convert images to PDF
- **PDF to JPG** — Convert PDF pages to images
- **Rotate PDF** — Rotate pages by 90°, 180°, or 270°
- **Delete Pages** — Remove specific pages
- **Extract Pages** — Extract page ranges into a new PDF

### PDF Convert (11 tools)
- PDF to Word (.docx), Excel (.xlsx), PowerPoint (.pptx)
- Word to PDF, Excel to PDF, PowerPoint to PDF
- HTML to PDF, TXT to PDF
- PNG to PDF, WebP to PDF
- PDF to PNG

### PDF Edit (9 tools)
- Crop PDF — Trim page margins
- Watermark PDF — Add text watermarks
- Add Page Numbers — Insert page numbers
- Add Text — Add text annotations
- Add Image — Insert images at any position
- Annotate PDF — Draw annotations
- Highlight — Highlight text
- Redact — Redact sensitive content
- Organize — Reorder pages

### PDF Security (3 tools)
- Protect PDF — Add password with AES-256 encryption
- Unlock PDF — Remove password protection
- Sign PDF — Draw or type a digital signature

### PDF OCR (2 tools)
- OCR PDF — Extract text from scanned PDFs (requires Tesseract)
- Scan to PDF — Convert images to searchable PDFs

### PDF Optimize (1 tool)
- Repair PDF — Fix corrupted or damaged PDF files

### AI Tools
- **Summarize PDF** — Generate concise summaries of PDF documents
- **Extract Text** — Extract and clean text from PDFs
- **Translate** — Translate text to any language
- **Ask Question** — Ask questions about PDF content

### AI Study Suite (9 tools)
- **Quiz Generator** — Generate multiple-choice quizzes from your PDFs
- **Flashcards** — Create interactive flashcards from study material
- **Study Notes** — Generate concise study notes
- **Study Guide** — Create comprehensive study guides
- **Question Bank** — Generate exam-style questions
- **Important Questions** — Identify key exam questions
- **Chapter Summary** — Summarize each chapter/page
- **Key Concepts** — Extract key concepts and definitions
- **Exam Prep** — Generate exam preparation material

### Additional Features
- User authentication & dashboard with job history
- Dark/light theme with system preference detection
- Responsive design with drag-and-drop file upload
- Real AI integration (OpenAI-compatible API)
- Render.com deployment support (`render.yaml`)

## Requirements

- Python 3.13+
- Django 5.2+
- Tesseract OCR (optional, for OCR tools)

## Installation

1. Clone or navigate to the project directory:
```powershell
cd C:\Pdf Master
```

2. Create a virtual environment:
```powershell
python -m venv venv
```

3. Activate the virtual environment:
```powershell
.\venv\Scripts\Activate.ps1
```

4. Install dependencies:
```powershell
pip install -r requirements.txt
```

5. Copy environment file:
```powershell
Copy-Item .env.example .env
```

6. Configure `.env` with your settings (OpenAI API key, Tesseract path, etc.)

## Database Setup

```powershell
python manage.py makemigrations
python manage.py migrate
```

## Run Server

```powershell
python manage.py runserver
```

Visit http://127.0.0.1:8000/ in your browser.

## Run Tests

```powershell
python manage.py test
```

## Create Superuser

```powershell
python manage.py createsuperuser
```

Then visit http://127.0.0.1:8000/admin/

## Deployment to Render

A `render.yaml` is included for one-click deployment. The service automatically handles:
- Python dependency installation
- Database migrations
- Static file collection
- Tesseract OCR installation

## Project Structure

```
PDFMaster/
    manage.py
    requirements.txt
    .env.example
    render.yaml
    README.md
    config/
        settings.py
        urls.py
        wsgi.py
        asgi.py
    core/
        views.py
        urls.py
        admin.py
        sitemaps.py
    pdf_tools/
        views.py          # All PDF tool views
        urls.py           # URL routing for 40+ tools
        forms.py          # Form definitions for all upload/validation
        models.py         # ProcessingJob model
        admin.py
        tests.py
        services/
            merge.py
            split.py
            compress.py
            jpg_to_pdf.py
            pdf_to_jpg.py
            rotate.py
            delete_pages.py
            extract_pages.py
            convert/
                pdf_to_word.py     # pdf_to_word, pdf_to_excel, pdf_to_ppt
                word_to_pdf.py     # word_to_pdf, excel_to_pdf, pptx_to_pdf
                image_convert.py   # html_to_pdf, txt_to_pdf, image_to_pdf
                pdf_to_image.py    # pdf_to_png, pdf_to_jpg
            edit/
                crop.py
                watermark.py
                add_text.py
                add_image.py
                annotate.py
                highlight.py
                redact.py
                organize.py
                page_numbers.py
            ocr/
                ocr.py             # OCR, scan_to_pdf
            security/
                protect.py
                unlock.py
                signature.py       # sign_pdf, decode_signature_image
            optimize/
                repair.py
            utils.py
    ai_tools/
        views.py          # AI tool + Study suite views
        urls.py           # URL routing
        forms.py          # AI form definitions
        models.py         # AIRequest model
        admin.py
        services/
            __init__.py
            ai_provider.py    # Provider abstraction (OpenAI)
            pdf_ai.py          # AI service functions
            study_ai.py        # AI study suite services
    templates/
        base.html
        home.html
        tools.html          # Categorized tool listing
        pricing.html
        faq.html
        dashboard.html
        pdf_tools/
            config_form.html   # Shared template for all PDF tools
            image_upload.html  # Shared template for image upload tools
            edit/add_image.html
            security/sign.html
        ai_tools/
            ai_tools.html
            study_form.html
            quiz_result.html
            flashcard_result.html
    static/
        css/
            style.css        # Full design system with dark/light themes
        js/
            main.js          # Drag-drop, theme toggle, file list UI
    media/
        temp/
```

## Security

- File size limits enforced
- File extension validation
- MIME type validation
- Actual PDF/image validation (magic bytes)
- Safe random filenames
- Temporary file cleanup after processing
- Path traversal protection
- No file storage after processing (ephemeral)

## License

MIT
