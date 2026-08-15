# PDFMaster

All Your PDF Tools in One Place

A professional Django-based web application for PDF processing tools including merge, split, compress, convert, rotate, delete pages, and extract pages.

## Features

- Merge PDF files
- Split PDF by page ranges
- Compress PDF files
- Convert JPG/PNG to PDF
- Convert PDF to JPG images
- Rotate PDF pages
- Delete PDF pages
- Extract PDF pages
- User authentication
- Dashboard with job history
- Responsive design

## Requirements

- Python 3.13+
- Django 6.1+
- Windows, macOS, or Linux

## Installation

1. Clone or navigate to the project directory:
```powershell
cd C:\Users\Ali\.cline\data\workspaces\chat\PDFMaster
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

6. Configure `.env` with your settings.

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

## Project Structure

PDFMaster/
    manage.py
    requirements.txt
    .env.example
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
        tests.py
    pdf_tools/
        views.py
        urls.py
        forms.py
        models.py
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
    templates/
        base.html
        home.html
        tools.html
        pricing.html
        faq.html
        dashboard.html
        404.html
        403.html
        500.html
        pdf_tools/
            merge.html
            split.html
            compress.html
            jpg_to_pdf.html
            pdf_to_jpg.html
            rotate.html
            delete_pages.html
            extract_pages.html
    static/
        css/
            style.css
        js/
            main.js
    media/
        temp/

## Security

- File size limits enforced
- File extension validation
- MIME type validation
- Actual PDF/image validation
- Safe random filenames
- Temporary file cleanup
- Path traversal protection
- No file storage after processing

## License

MIT