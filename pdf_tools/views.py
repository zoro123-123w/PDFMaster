import os
import uuid
import logging
from django import forms
from django.forms import Form
from django.conf import settings
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse, FileResponse, Http404
from django.urls import reverse
from django.utils import timezone
from .models import ProcessingJob
from .forms import (
    PDFUploadForm, SinglePDFUploadForm, ImageUploadForm, PageRangeForm,
    RotationForm, WordUploadForm, ExcelUploadForm,
    PowerPointUploadForm, HTMLUploadForm, TextFileUploadForm,
    PasswordForm, ProtectForm, RedactForm, CropForm, WatermarkForm,
    PageNumberForm, OrganizeForm, OcrForm, SignatureForm,
    AddTextForm, AddImageForm, AnnotateForm, HighlightForm,
    PPTUploadForm, ImageUploadAnyForm,
)
from .services.merge import merge_pdf_service
from .services.split import split_pdf_service
from .services.compress import compress_pdf_service
from .services.jpg_to_pdf import jpg_to_pdf_service
from .services.pdf_to_jpg import pdf_to_jpg_service, pdf_to_png_service
from .services.rotate import rotate_pdf_service
from .services.delete_pages import delete_pages_service
from .services.extract_pages import extract_pages_service
from .services.convert import (
    pdf_to_word as _pdf_to_word, word_to_pdf as _word_to_pdf,
    pdf_to_excel as _pdf_to_excel, pdf_to_ppt as _pdf_to_ppt,
    html_to_pdf as _html_to_pdf, txt_to_pdf as _txt_to_pdf,
    excel_to_pdf as _excel_to_pdf, pptx_to_pdf as _pptx_to_pdf,
    image_to_pdf as _image_to_pdf,
)
from .services.edit import (
    crop_pdf as _crop_pdf, watermark_pdf as _watermark_pdf,
    add_page_numbers as _add_page_numbers, organize_pdf as _organize_pdf,
    repair_pdf as _repair_pdf,
    add_text_to_pdf as _add_text_to_pdf,
    add_image_to_pdf as _add_image_to_pdf,
    annotate_pdf as _annotate_pdf, highlight_pdf as _highlight_pdf,
)
from .services.ocr import ocr_pdf, OCRNotConfiguredError, tesseract_available
from .services.security import (
    protect_pdf as _protect_pdf, unlock_pdf as _unlock_pdf, redact_pdf as _redact_pdf,
)
from .services.signature import sign_pdf, SignatureError, decode_signature_image
from .services.utils import create_output_path


logger = logging.getLogger(__name__)


def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    return x_forwarded_for.split(',')[0] if x_forwarded_for else request.META.get('REMOTE_ADDR')


def validate_pdf(file_obj):
    if file_obj.size > settings.MAX_UPLOAD_SIZE:
        return False, f"File exceeds maximum size of {settings.MAX_UPLOAD_SIZE // (1024*1024)} MB"
    if not file_obj.name.lower().endswith('.pdf'):
        return False, "File is not a PDF"
    file_obj.seek(0)
    header = file_obj.read(5)
    file_obj.seek(0)
    if not header.startswith(b'%PDF-'):
        return False, "Invalid PDF file"
    try:
        import pypdf
        pypdf.PdfReader(file_obj)
        file_obj.seek(0)
        return True, None
    except Exception:
        return False, "Invalid PDF file"


def validate_image(file_obj):
    if file_obj.size > settings.MAX_UPLOAD_SIZE:
        return False, f"File exceeds maximum size of {settings.MAX_UPLOAD_SIZE // (1024*1024)} MB"
    allowed = ['jpg', 'jpeg', 'png']
    if not any(file_obj.name.lower().endswith(ext) for ext in allowed):
        return False, "File is not a valid image (JPG, JPEG, PNG)"
    try:
        from PIL import Image
        img = Image.open(file_obj)
        img.verify()
        file_obj.seek(0)
        return True, None
    except Exception:
        return False, "Invalid image file"


def validate_image_any(file_obj):
    """Validate any image format including WebP and GIF."""
    if file_obj.size > settings.MAX_UPLOAD_SIZE:
        return False, f"File exceeds maximum size of {settings.MAX_UPLOAD_SIZE // (1024*1024)} MB"
    allowed = ['jpg', 'jpeg', 'png', 'webp', 'gif', 'bmp', 'tiff']
    if not any(file_obj.name.lower().endswith(ext) for ext in allowed):
        return False, "File is not a valid image"
    try:
        from PIL import Image
        img = Image.open(file_obj)
        img.verify()
        file_obj.seek(0)
        return True, None
    except Exception:
        return False, "Invalid image file"


def _validate_document(file_obj, extensions, label):
    if file_obj.size > settings.MAX_UPLOAD_SIZE:
        return False, f"File exceeds maximum size of {settings.MAX_UPLOAD_SIZE // (1024*1024)} MB"
    if not any(file_obj.name.lower().endswith(ext) for ext in extensions):
        return False, f"File is not a valid {label}"
    return True, None


def validate_docx(file_obj):
    return _validate_document(file_obj, ['.docx'], 'Word document')


def validate_xlsx(file_obj):
    return _validate_document(file_obj, ['.xlsx', '.xls'], 'Excel file')


def validate_pptx(file_obj):
    return _validate_document(file_obj, ['.pptx', '.ppt'], 'PowerPoint file')


def validate_html(file_obj):
    return _validate_document(file_obj, ['.html', '.htm'], 'HTML file')


def validate_txt(file_obj):
    return _validate_document(file_obj, ['.txt'], 'text file')


def save_uploaded_file(file_obj):
    ext = os.path.splitext(file_obj.name)[1]
    filename = f"{uuid.uuid4().hex}{ext}"
    temp_dir = os.path.join(settings.MEDIA_ROOT, 'temp')
    os.makedirs(temp_dir, exist_ok=True)
    path = os.path.join(temp_dir, filename)
    with open(path, 'wb+') as f:
        for chunk in file_obj.chunks():
            f.write(chunk)
    return path


PDF_TOOL_CATEGORIES = [
    {
        'name': 'PDF Organize',
        'slug': 'organize',
        'description': 'Combine, split, and reorder your PDF documents',
        'tools': [
            {'name': 'Merge PDF', 'url': 'merge_pdf', 'description': 'Combine multiple PDFs into one document', 'icon': '📄'},
            {'name': 'Split PDF', 'url': 'split_pdf', 'description': 'Extract pages or ranges from a PDF', 'icon': '✂️'},
            {'name': 'Delete PDF Pages', 'url': 'delete_pages', 'description': 'Remove specific pages from a PDF', 'icon': '🗑️'},
            {'name': 'Extract PDF Pages', 'url': 'extract_pages', 'description': 'Extract selected pages to a new PDF', 'icon': '📑'},
            {'name': 'Organize/Reorder Pages', 'url': 'organize_pdf', 'description': 'Reorder and rotate PDF pages', 'icon': '🔀'},
        ],
    },
    {
        'name': 'PDF Convert',
        'slug': 'convert',
        'description': 'Convert PDFs to and from other formats',
        'tools': [
            {'name': 'PDF to Word', 'url': 'pdf_to_word', 'description': 'Convert PDF to editable DOCX', 'icon': '📄'},
            {'name': 'PDF to Excel', 'url': 'pdf_to_excel', 'description': 'Convert PDF tables to Excel', 'icon': '📊'},
            {'name': 'PDF to PowerPoint', 'url': 'pdf_to_ppt', 'description': 'Convert PDF to PowerPoint slides', 'icon': '📊'},
            {'name': 'Word to PDF', 'url': 'word_to_pdf', 'description': 'Convert DOCX to PDF', 'icon': '📝'},
            {'name': 'Excel to PDF', 'url': 'excel_to_pdf', 'description': 'Convert XLSX to PDF', 'icon': '📈'},
            {'name': 'PowerPoint to PDF', 'url': 'ppt_to_pdf', 'description': 'Convert PPTX to PDF', 'icon': '📊'},
            {'name': 'HTML to PDF', 'url': 'html_to_pdf', 'description': 'Convert HTML files to PDF', 'icon': '🌐'},
            {'name': 'TXT to PDF', 'url': 'txt_to_pdf', 'description': 'Convert text files to PDF', 'icon': '📝'},
            {'name': 'JPG to PDF', 'url': 'jpg_to_pdf', 'description': 'Convert JPG/PNG images to PDF', 'icon': '🖼️'},
            {'name': 'PNG to PDF', 'url': 'png_to_pdf', 'description': 'Convert PNG images to PDF', 'icon': '🖼️'},
            {'name': 'WebP to PDF', 'url': 'webp_to_pdf', 'description': 'Convert WebP images to PDF', 'icon': '🖼️'},
            {'name': 'PDF to JPG', 'url': 'pdf_to_jpg', 'description': 'Convert PDF pages to JPG images', 'icon': '📷'},
            {'name': 'PDF to PNG', 'url': 'pdf_to_png', 'description': 'Convert PDF pages to PNG images', 'icon': '📷'},
        ],
    },
    {
        'name': 'PDF Edit',
        'slug': 'edit',
        'description': 'Edit, annotate, and enhance your PDF documents',
        'tools': [
            {'name': 'Crop PDF', 'url': 'crop_pdf', 'description': 'Crop margins from PDF pages', 'icon': '✂️'},
            {'name': 'Watermark PDF', 'url': 'watermark_pdf', 'description': 'Add text watermark to PDF pages', 'icon': '💧'},
            {'name': 'Add Page Numbers', 'url': 'add_page_numbers', 'description': 'Add page numbers to PDF', 'icon': '🔢'},
            {'name': 'Add Text to PDF', 'url': 'add_text_to_pdf', 'description': 'Insert text at any position', 'icon': '📝'},
            {'name': 'Add Image to PDF', 'url': 'add_image_to_pdf', 'description': 'Insert images into PDF', 'icon': '🖼️'},
            {'name': 'Annotate PDF', 'url': 'annotate_pdf', 'description': 'Add text annotations to PDF', 'icon': '📝'},
            {'name': 'Highlight PDF', 'url': 'highlight_pdf', 'description': 'Highlight text in PDF', 'icon': '🎨'},
            {'name': 'Redact PDF', 'url': 'redact_pdf', 'description': 'Permanently remove text from PDF', 'icon': '🔴'},
        ],
    },
    {
        'name': 'PDF Security',
        'slug': 'security',
        'description': 'Protect, unlock, and sign your PDF documents',
        'tools': [
            {'name': 'Protect PDF', 'url': 'protect_pdf', 'description': 'Add password protection to PDF', 'icon': '🔒'},
            {'name': 'Unlock PDF', 'url': 'unlock_pdf', 'description': 'Remove password from PDF', 'icon': '🔓'},
            {'name': 'Sign PDF', 'url': 'sign_pdf', 'description': 'Add e-signature to PDF', 'icon': '✍️'},
        ],
    },
    {
        'name': 'PDF Optimize',
        'slug': 'optimize',
        'description': 'Compress and repair your PDF documents',
        'tools': [
            {'name': 'Compress PDF', 'url': 'compress_pdf', 'description': 'Reduce PDF file size while preserving quality', 'icon': '🗜️'},
            {'name': 'Repair PDF', 'url': 'repair_pdf', 'description': 'Fix corrupted or damaged PDFs', 'icon': '🛠️'},
        ],
    },
    {
        'name': 'PDF OCR',
        'slug': 'ocr',
        'description': 'Recognize text in scanned PDFs',
        'tools': [
            {'name': 'OCR PDF', 'url': 'ocr_pdf', 'description': 'Make scanned PDFs searchable', 'icon': '👁️'},
            {'name': 'Scan to Searchable PDF', 'url': 'scan_to_pdf', 'description': 'Convert images to searchable PDF', 'icon': '📸'},
        ],
    },
]

# Flat list kept for backwards compatibility and imports from other apps.
PDF_TOOLS = [tool for cat in PDF_TOOL_CATEGORIES for tool in cat['tools']]


def tools_list(request):
    return render(request, 'tools.html', {
        'tools': PDF_TOOLS,
        'categories': PDF_TOOL_CATEGORIES,
    })


def merge_pdf(request):
    if request.method == 'POST':
        form = PDFUploadForm(request.POST, request.FILES)
        if form.is_valid():
            files = request.FILES.getlist('files')
            if len(files) < 2:
                messages.error(request, "Please upload at least 2 PDF files")
                return render(request, 'pdf_tools/merge.html', {'form': form})
            file_paths = []
            for f in files:
                valid, err = validate_pdf(f)
                if not valid:
                    messages.error(request, err)
                    return render(request, 'pdf_tools/merge.html', {'form': form})
                file_paths.append(save_uploaded_file(f))
            try:
                output_path = merge_pdf_service(file_paths)
                job = ProcessingJob.objects.create(
                    user=request.user if request.user.is_authenticated else None,
                    tool_name='merge_pdf',
                    original_filename='merged.pdf',
                    status='COMPLETED',
                    completed_at=timezone.now(),
                    output_file=output_path
                )
                for p in file_paths:
                    try:
                        os.remove(p)
                    except OSError:
                        pass
                return redirect(reverse('download_file', args=[job.id]))
            except Exception as e:
                messages.error(request, "Something went wrong while merging PDFs")
                for p in file_paths:
                    try:
                        os.remove(p)
                    except OSError:
                        pass
    else:
        form = PDFUploadForm()
    return render(request, 'pdf_tools/merge.html', {'form': form})


def split_pdf(request):
    if request.method == 'POST':
        form = SinglePDFUploadForm(request.POST, request.FILES)
        range_form = PageRangeForm(request.POST)
        if form.is_valid() and range_form.is_valid():
            f = request.FILES['file']
            valid, err = validate_pdf(f)
            if not valid:
                messages.error(request, err)
                return render(request, 'pdf_tools/split.html', {'form': form, 'range_form': range_form})
            file_path = save_uploaded_file(f)
            try:
                ranges_str = range_form.cleaned_data['pages']
                output_path = split_pdf_service(file_path, ranges_str)
                job = ProcessingJob.objects.create(
                    user=request.user if request.user.is_authenticated else None,
                    tool_name='split_pdf',
                    original_filename=f.name,
                    status='COMPLETED',
                    completed_at=timezone.now(),
                    output_file=output_path
                )
                try:
                    os.remove(file_path)
                except OSError:
                    pass
                return redirect(reverse('download_file', args=[job.id]))
            except ValueError as e:
                messages.error(request, str(e))
            except Exception:
                messages.error(request, "Something went wrong while splitting the PDF")
            finally:
                try:
                    os.remove(file_path)
                except OSError:
                    pass
    else:
        form = SinglePDFUploadForm()
        range_form = PageRangeForm()
    return render(request, 'pdf_tools/split.html', {'form': form, 'range_form': range_form})


def compress_pdf(request):
    if request.method == 'POST':
        form = SinglePDFUploadForm(request.POST, request.FILES)
        if form.is_valid():
            f = request.FILES['file']
            valid, err = validate_pdf(f)
            if not valid:
                messages.error(request, err)
                return render(request, 'pdf_tools/compress.html', {'form': form})
            file_path = save_uploaded_file(f)
            original_size = os.path.getsize(file_path)
            try:
                output_path = compress_pdf_service(file_path)
                compressed_size = os.path.getsize(output_path)
                ratio = ((original_size - compressed_size) / original_size) * 100 if original_size > 0 else 0
                job = ProcessingJob.objects.create(
                    user=request.user if request.user.is_authenticated else None,
                    tool_name='compress_pdf',
                    original_filename=f.name,
                    status='COMPLETED',
                    completed_at=timezone.now(),
                    output_file=output_path
                )
                try:
                    os.remove(file_path)
                except OSError:
                    pass
                return render(request, 'pdf_tools/compress.html', {
                    'form': form,
                    'original_size': original_size,
                    'compressed_size': compressed_size,
                    'ratio': ratio,
                    'job_id': job.id,
                })
            except Exception:
                messages.error(request, "Something went wrong while compressing the PDF")
            finally:
                try:
                    os.remove(file_path)
                except OSError:
                    pass
    else:
        form = SinglePDFUploadForm()
    return render(request, 'pdf_tools/compress.html', {'form': form})


def jpg_to_pdf(request):
    if request.method == 'POST':
        form = ImageUploadForm(request.POST, request.FILES)
        if form.is_valid():
            files = request.FILES.getlist('files')
            if not files:
                messages.error(request, "Please upload at least one image")
                return render(request, 'pdf_tools/jpg_to_pdf.html', {'form': form})
            file_paths = []
            for f in files:
                valid, err = validate_image(f)
                if not valid:
                    messages.error(request, err)
                    return render(request, 'pdf_tools/jpg_to_pdf.html', {'form': form})
                file_paths.append(save_uploaded_file(f))
            try:
                output_path = jpg_to_pdf_service(file_paths)
                job = ProcessingJob.objects.create(
                    user=request.user if request.user.is_authenticated else None,
                    tool_name='jpg_to_pdf',
                    original_filename='images.pdf',
                    status='COMPLETED',
                    completed_at=timezone.now(),
                    output_file=output_path
                )
                for p in file_paths:
                    try:
                        os.remove(p)
                    except OSError:
                        pass
                return redirect(reverse('download_file', args=[job.id]))
            except Exception:
                messages.error(request, "Something went wrong while converting images to PDF")
            finally:
                for p in file_paths:
                    try:
                        os.remove(p)
                    except OSError:
                        pass
    else:
        form = ImageUploadForm()
    return render(request, 'pdf_tools/jpg_to_pdf.html', {'form': form})


def pdf_to_jpg(request):
    if request.method == 'POST':
        form = SinglePDFUploadForm(request.POST, request.FILES)
        if form.is_valid():
            f = request.FILES['file']
            valid, err = validate_pdf(f)
            if not valid:
                messages.error(request, err)
                return render(request, 'pdf_tools/pdf_to_jpg.html', {'form': form})
            file_path = save_uploaded_file(f)
            try:
                output_paths = pdf_to_jpg_service(file_path)
                job = ProcessingJob.objects.create(
                    user=request.user if request.user.is_authenticated else None,
                    tool_name='pdf_to_jpg',
                    original_filename=f.name,
                    status='COMPLETED',
                    completed_at=timezone.now(),
                    output_file=output_paths[0] if output_paths else ''
                )
                try:
                    os.remove(file_path)
                except OSError:
                    pass
                if len(output_paths) == 1:
                    return redirect(reverse('download_file', args=[job.id]))
                else:
                    zip_path = os.path.join(settings.MEDIA_ROOT, 'temp', f'{uuid.uuid4().hex}.zip')
                    import zipfile as zf
                    with zf.ZipFile(zip_path, 'w') as zipf:
                        for img_path in output_paths:
                            zipf.write(img_path, os.path.basename(img_path))
                    response = FileResponse(open(zip_path, 'rb'), as_attachment=True, filename='converted_images.zip')
                    for p in output_paths:
                        try:
                            os.remove(p)
                        except OSError:
                            pass
                    return response
            except Exception:
                messages.error(request, "Something went wrong while converting PDF to images")
            finally:
                try:
                    os.remove(file_path)
                except OSError:
                    pass
    else:
        form = SinglePDFUploadForm()
    return render(request, 'pdf_tools/pdf_to_jpg.html', {'form': form})


def rotate_pdf(request):
    if request.method == 'POST':
        form = SinglePDFUploadForm(request.POST, request.FILES)
        rotation_form = RotationForm(request.POST)
        if form.is_valid() and rotation_form.is_valid():
            f = request.FILES['file']
            valid, err = validate_pdf(f)
            if not valid:
                messages.error(request, err)
                return render(request, 'pdf_tools/rotate.html', {'form': form, 'rotation_form': rotation_form})
            file_path = save_uploaded_file(f)
            try:
                angle = int(rotation_form.cleaned_data['angle'])
                output_path = rotate_pdf_service(file_path, angle)
                job = ProcessingJob.objects.create(
                    user=request.user if request.user.is_authenticated else None,
                    tool_name='rotate_pdf',
                    original_filename=f.name,
                    status='COMPLETED',
                    completed_at=timezone.now(),
                    output_file=output_path
                )
                try:
                    os.remove(file_path)
                except OSError:
                    pass
                return redirect(reverse('download_file', args=[job.id]))
            except Exception:
                messages.error(request, "Something went wrong while rotating the PDF")
            finally:
                try:
                    os.remove(file_path)
                except OSError:
                    pass
    else:
        form = SinglePDFUploadForm()
        rotation_form = RotationForm()
    return render(request, 'pdf_tools/rotate.html', {'form': form, 'rotation_form': rotation_form})


def delete_pages(request):
    if request.method == 'POST':
        form = SinglePDFUploadForm(request.POST, request.FILES)
        range_form = PageRangeForm(request.POST)
        if form.is_valid() and range_form.is_valid():
            f = request.FILES['file']
            valid, err = validate_pdf(f)
            if not valid:
                messages.error(request, err)
                return render(request, 'pdf_tools/delete_pages.html', {'form': form, 'range_form': range_form})
            file_path = save_uploaded_file(f)
            try:
                pages_str = range_form.cleaned_data['pages']
                output_path = delete_pages_service(file_path, pages_str)
                job = ProcessingJob.objects.create(
                    user=request.user if request.user.is_authenticated else None,
                    tool_name='delete_pages',
                    original_filename=f.name,
                    status='COMPLETED',
                    completed_at=timezone.now(),
                    output_file=output_path
                )
                try:
                    os.remove(file_path)
                except OSError:
                    pass
                return redirect(reverse('download_file', args=[job.id]))
            except ValueError as e:
                messages.error(request, str(e))
            except Exception:
                messages.error(request, "Something went wrong while deleting pages")
            finally:
                try:
                    os.remove(file_path)
                except OSError:
                    pass
    else:
        form = SinglePDFUploadForm()
        range_form = PageRangeForm()
    return render(request, 'pdf_tools/delete_pages.html', {'form': form, 'range_form': range_form})


def extract_pages(request):
    if request.method == 'POST':
        form = SinglePDFUploadForm(request.POST, request.FILES)
        range_form = PageRangeForm(request.POST)
        if form.is_valid() and range_form.is_valid():
            f = request.FILES['file']
            valid, err = validate_pdf(f)
            if not valid:
                messages.error(request, err)
                return render(request, 'pdf_tools/extract_pages.html', {'form': form, 'range_form': range_form})
            file_path = save_uploaded_file(f)
            try:
                pages_str = range_form.cleaned_data['pages']
                output_path = extract_pages_service(file_path, pages_str)
                job = ProcessingJob.objects.create(
                    user=request.user if request.user.is_authenticated else None,
                    tool_name='extract_pages',
                    original_filename=f.name,
                    status='COMPLETED',
                    completed_at=timezone.now(),
                    output_file=output_path
                )
                try:
                    os.remove(file_path)
                except OSError:
                    pass
                return redirect(reverse('download_file', args=[job.id]))
            except ValueError as e:
                messages.error(request, str(e))
            except Exception:
                messages.error(request, "Something went wrong while extracting pages")
            finally:
                try:
                    os.remove(file_path)
                except OSError:
                    pass
    else:
        form = SinglePDFUploadForm()
        range_form = PageRangeForm()
    return render(request, 'pdf_tools/extract_pages.html', {'form': form, 'range_form': range_form})


def download_file(request, job_id):
    try:
        job = ProcessingJob.objects.get(id=job_id)
        if not job.output_file or not os.path.exists(job.output_file):
            messages.error(request, "File not found or has expired")
            return redirect('home')
        download_name = job.output_filename or os.path.basename(job.output_file)
        response = FileResponse(open(job.output_file, 'rb'), as_attachment=True, filename=download_name)
        try:
            os.remove(job.output_file)
            job.output_file = ''
            job.save()
        except OSError:
            pass
        return response
    except ProcessingJob.DoesNotExist:
        messages.error(request, "Job not found")
        return redirect('home')


# --------------------------------------------------------------------------- #
# Helper for tools that upload a single PDF + optional config form
# --------------------------------------------------------------------------- #

def _handle_pdf_config_tool(request, tool_name, tool_label, config_form_class,
                            service_fn, output_ext, template, validate_fn=None,
                            needs_config=True, submit_label=None, tool_subtitle=None,
                            file_accept='.pdf'):
    """Generic handler: single PDF upload + optional config form + service call.

    ``validate_fn`` defaults to :func:`validate_pdf`.
    ``output_ext`` is appended to the output filename (e.g. '.docx').
    Returns either a ``redirect`` (success), ``HttpResponse`` (zip download),
    or ``render`` (GET / error).
    """
    if validate_fn is None:
        validate_fn = validate_pdf
    if submit_label is None:
        submit_label = tool_label

    upload_form_kwargs = {'data': request.POST, 'files': request.FILES} if request.method == 'POST' else {}
    upload_form = SinglePDFUploadForm(**upload_form_kwargs)
    config_form = config_form_class(request.POST) if request.method == 'POST' else config_form_class()

    if request.method == 'POST' and upload_form.is_valid():
        if needs_config and not config_form.is_valid():
            return render(request, template, {
                'form': upload_form, 'config_form': config_form, 'tool_name': tool_label,
                'submit_label': submit_label, 'tool_subtitle': tool_subtitle,
                'file_accept': file_accept,
            })
        f = request.FILES['file']
        valid, err = validate_fn(f)
        if not valid:
            messages.error(request, err)
            return render(request, template, {
                'form': upload_form, 'config_form': config_form, 'tool_name': tool_label,
                'submit_label': submit_label, 'tool_subtitle': tool_subtitle,
                'file_accept': file_accept,
            })
        file_path = save_uploaded_file(f)
        try:
            data = config_form.cleaned_data if needs_config else {}
            result = service_fn(file_path, data)
            if isinstance(result, tuple):
                output_path, total = result
            elif isinstance(result, list):
                output_path = result
            else:
                output_path = result
            output_filename = os.path.splitext(f.name)[0] + output_ext
            job = ProcessingJob.objects.create(
                user=request.user if request.user.is_authenticated else None,
                tool_name=tool_name,
                original_filename=f.name,
                status='COMPLETED',
                completed_at=timezone.now(),
                output_file=output_path,
                output_filename=output_filename,
            )
            try:
                os.remove(file_path)
            except OSError:
                pass
            if isinstance(output_path, list) and len(output_path) > 1:
                return _download_image_zip(output_path)
            return redirect(reverse('download_file', args=[job.id]))
        except ValueError as e:
            messages.error(request, str(e))
        except Exception:
            logger.exception('PDF processing failed for tool %s', tool_name)
            messages.error(request, "Something went wrong while processing the PDF")
        finally:
            try:
                os.remove(file_path)
            except OSError:
                pass
    return render(request, template, {
        'form': upload_form, 'config_form': config_form, 'tool_name': tool_label,
        'submit_label': submit_label, 'tool_subtitle': tool_subtitle,
        'file_accept': file_accept,
    })


def _download_image_zip(image_paths):
    """Zip multiple image paths and return a streaming download response."""
    import zipfile as zf
    zip_path = os.path.join(settings.MEDIA_ROOT, 'temp', f'{uuid.uuid4().hex}.zip')
    with zf.ZipFile(zip_path, 'w') as zipf:
        for img_path in image_paths:
            zipf.write(img_path, os.path.basename(img_path))
    response = FileResponse(open(zip_path, 'rb'), as_attachment=True,
                            filename='converted_images.zip')
    for p in image_paths:
        try:
            os.remove(p)
        except OSError:
            pass
    try:
        os.remove(zip_path)
    except OSError:
        pass
    return response


# --------------------------------------------------------------------------- #
# PDF Conversion views
# --------------------------------------------------------------------------- #

def pdf_to_word(request):
    return _handle_pdf_config_tool(
        request, 'pdf_to_word', 'PDF to Word', Form, _pdf_to_word,
        '.docx', 'pdf_tools/config_form.html', needs_config=False,
        submit_label='Convert to Word')


def pdf_to_excel(request):
    return _handle_pdf_config_tool(
        request, 'pdf_to_excel', 'PDF to Excel', Form, _pdf_to_excel,
        '.xlsx', 'pdf_tools/config_form.html', needs_config=False,
        submit_label='Convert to Excel')


def pdf_to_ppt(request):
    return _handle_pdf_config_tool(
        request, 'pdf_to_ppt', 'PDF to PowerPoint', Form, _pdf_to_ppt,
        '.pptx', 'pdf_tools/config_form.html', needs_config=False,
        submit_label='Convert to PowerPoint')


def word_to_pdf(request):
    return _handle_pdf_config_tool(
        request, 'word_to_pdf', 'Word to PDF', Form, _word_to_pdf,
        '.pdf', 'pdf_tools/config_form.html',
        validate_fn=validate_docx, needs_config=False,
        file_accept='.docx', submit_label='Convert to PDF')


def excel_to_pdf(request):
    return _handle_pdf_config_tool(
        request, 'excel_to_pdf', 'Excel to PDF', Form, _excel_to_pdf,
        '.pdf', 'pdf_tools/config_form.html',
        validate_fn=validate_xlsx, needs_config=False,
        file_accept='.xlsx,.xls', submit_label='Convert to PDF')


def ppt_to_pdf(request):
    return _handle_pdf_config_tool(
        request, 'ppt_to_pdf', 'PowerPoint to PDF', Form, _pptx_to_pdf,
        '.pdf', 'pdf_tools/config_form.html',
        validate_fn=validate_pptx, needs_config=False,
        file_accept='.pptx,.ppt', submit_label='Convert to PDF')


def html_to_pdf(request):
    return _handle_pdf_config_tool(
        request, 'html_to_pdf', 'HTML to PDF', Form, _html_to_pdf,
        '.pdf', 'pdf_tools/config_form.html',
        validate_fn=validate_html, needs_config=False,
        file_accept='.html,.htm', submit_label='Convert to PDF')


def txt_to_pdf(request):
    return _handle_pdf_config_tool(
        request, 'txt_to_pdf', 'TXT to PDF', Form, _txt_to_pdf,
        '.pdf', 'pdf_tools/config_form.html',
        validate_fn=validate_txt, needs_config=False,
        file_accept='.txt', submit_label='Convert to PDF')


def pdf_to_png(request):
    def _service(file_path, data):
        images = pdf_to_png_service(file_path)
        if len(images) == 1:
            return images[0]
        return images
    return _handle_pdf_config_tool(
        request, 'pdf_to_png', 'PDF to PNG', Form, _service,
        '.png', 'pdf_tools/config_form.html', needs_config=False,
        submit_label='Convert to PNG')


# --------------------------------------------------------------------------- #
# Image conversion views (PNG to PDF, WebP to PDF)
# --------------------------------------------------------------------------- #

def png_to_pdf(request):
    return _handle_image_to_pdf(request, 'png_to_pdf', 'PNG to PDF',
                                'pdf_tools/image_upload.html')


def webp_to_pdf(request):
    return _handle_image_to_pdf(request, 'webp_to_pdf', 'WebP to PDF',
                                'pdf_tools/image_upload.html')


def _handle_image_to_pdf(request, tool_name, tool_label, template):
    """Handler for image-to-PDF tools that reuse the image_to_pdf service."""
    form = ImageUploadForm(data=request.POST, files=request.FILES) if request.method == 'POST' else ImageUploadForm()
    if request.method == 'POST' and form.is_valid():
        files = request.FILES.getlist('files')
        if not files:
            messages.error(request, "Please upload at least one image")
            return render(request, template, {'form': form, 'tool_name': tool_label})
        file_paths = []
        for f in files:
            valid, err = validate_image_any(f)
            if not valid:
                messages.error(request, err)
                return render(request, template, {'form': form, 'tool_name': tool_label})
            file_paths.append(save_uploaded_file(f))
        try:
            output_path = image_to_pdf(file_paths)
            output_filename = os.path.splitext(files[0].name)[0] + '.pdf'
            job = ProcessingJob.objects.create(
                user=request.user if request.user.is_authenticated else None,
                tool_name=tool_name,
                original_filename=files[0].name,
                status='COMPLETED',
                completed_at=timezone.now(),
                output_file=output_path,
                output_filename=output_filename,
            )
            for p in file_paths:
                try:
                    os.remove(p)
                except OSError:
                    pass
            return redirect(reverse('download_file', args=[job.id]))
        except Exception:
            messages.error(request, "Something went wrong while converting images to PDF")
        finally:
            for p in file_paths:
                try:
                    os.remove(p)
                except OSError:
                    pass
    return render(request, template, {'form': form, 'tool_name': tool_label, 'submit_label': tool_label})


# --------------------------------------------------------------------------- #
# PDF Editing views
# --------------------------------------------------------------------------- #

def crop_pdf(request):
    return _handle_pdf_config_tool(
        request, 'crop_pdf', 'Crop PDF', CropForm, _crop_pdf,
        '.pdf', 'pdf_tools/config_form.html')


def watermark_pdf(request):
    return _handle_pdf_config_tool(
        request, 'watermark_pdf', 'Watermark PDF', WatermarkForm, _watermark_pdf,
        '.pdf', 'pdf_tools/config_form.html')


def add_page_numbers(request):
    return _handle_pdf_config_tool(
        request, 'add_page_numbers', 'Add Page Numbers', PageNumberForm, _add_page_numbers,
        '.pdf', 'pdf_tools/config_form.html')


def add_text_to_pdf(request):
    return _handle_pdf_config_tool(
        request, 'add_text_to_pdf', 'Add Text to PDF', AddTextForm, _add_text_to_pdf,
        '.pdf', 'pdf_tools/config_form.html')


def add_image_to_pdf(request):
    upload_form = SinglePDFUploadForm()
    image_form = AddImageForm()
    if request.method == 'POST':
        upload_form = SinglePDFUploadForm(request.POST, request.FILES)
        image_form = AddImageForm(request.POST, request.FILES)
        if upload_form.is_valid() and image_form.is_valid():
            pdf_file = request.FILES['file']
            image_file = request.FILES['image']
            v1, e1 = validate_pdf(pdf_file)
            if not v1:
                messages.error(request, e1)
                return render(request, 'pdf_tools/edit/add_image.html',
                              {'form': upload_form, 'image_form': image_form})
            v2, e2 = validate_image_any(image_file)
            if not v2:
                messages.error(request, e2)
                return render(request, 'pdf_tools/edit/add_image.html',
                              {'form': upload_form, 'image_form': image_form})
            pdf_path = save_uploaded_file(pdf_file)
            img_path = save_uploaded_file(image_file)
            try:
                data = image_form.cleaned_data
                output_path = _add_image_to_pdf(pdf_path, img_path, data)
                output_filename = os.path.splitext(pdf_file.name)[0] + '.pdf'
                job = ProcessingJob.objects.create(
                    user=request.user if request.user.is_authenticated else None,
                    tool_name='add_image_to_pdf',
                    original_filename=pdf_file.name,
                    status='COMPLETED',
                    completed_at=timezone.now(),
                    output_file=output_path,
                    output_filename=output_filename,
                )
                try:
                    os.remove(pdf_path)
                except OSError:
                    pass
                try:
                    os.remove(img_path)
                except OSError:
                    pass
                return redirect(reverse('download_file', args=[job.id]))
            except ValueError as e:
                messages.error(request, str(e))
            except Exception:
                messages.error(request, "Something went wrong while adding the image")
            finally:
                try:
                    os.remove(pdf_path)
                except OSError:
                    pass
                try:
                    os.remove(img_path)
                except OSError:
                    pass
    return render(request, 'pdf_tools/edit/add_image.html',
                  {'form': upload_form, 'image_form': image_form})


def annotate_pdf(request):
    return _handle_pdf_config_tool(
        request, 'annotate_pdf', 'Annotate PDF', AnnotateForm, _annotate_pdf,
        '.pdf', 'pdf_tools/config_form.html')


def highlight_pdf(request):
    return _handle_pdf_config_tool(
        request, 'highlight_pdf', 'Highlight PDF', HighlightForm, _highlight_pdf,
        '.pdf', 'pdf_tools/config_form.html')


def redact_pdf(request):
    return _handle_pdf_config_tool(
        request, 'redact_pdf', 'Redact PDF', RedactForm, _redact_pdf,
        '.pdf', 'pdf_tools/config_form.html')


def organize_pdf(request):
    return _handle_pdf_config_tool(
        request, 'organize_pdf', 'Organize/Reorder Pages', OrganizeForm, _organize_pdf,
        '.pdf', 'pdf_tools/config_form.html')


# --------------------------------------------------------------------------- #
# PDF Security views
# --------------------------------------------------------------------------- #

def protect_pdf(request):
    return _handle_pdf_config_tool(
        request, 'protect_pdf', 'Protect PDF', ProtectForm, _protect_pdf,
        '.pdf', 'pdf_tools/config_form.html')


def unlock_pdf(request):
    return _handle_pdf_config_tool(
        request, 'unlock_pdf', 'Unlock PDF', PasswordForm, _unlock_pdf,
        '.pdf', 'pdf_tools/config_form.html')


def sign_pdf_view(request):
    upload_form = SinglePDFUploadForm()
    sig_form = SignatureForm()
    if request.method == 'POST':
        upload_form = SinglePDFUploadForm(request.POST, request.FILES)
        sig_form = SignatureForm(request.POST)
        if upload_form.is_valid() and sig_form.is_valid():
            pdf_file = request.FILES['file']
            valid, err = validate_pdf(pdf_file)
            if not valid:
                messages.error(request, err)
                return render(request, 'pdf_tools/security/sign.html',
                              {'form': upload_form, 'config_form': sig_form,
                               'tool_name': 'Sign PDF', 'submit_label': 'Sign PDF'})
            pdf_path = save_uploaded_file(pdf_file)
            try:
                data = sig_form.cleaned_data
                sig_bytes = decode_signature_image(data.get('signature_data', ''))
                output_path, total = sign_pdf(
                    pdf_path, sig_bytes,
                    page_no=data.get('page') or 1,
                    x_pct=data.get('sig_x'), y_pct=data.get('sig_y'),
                    width_pct=data.get('sig_width'),
                )
                output_filename = os.path.splitext(pdf_file.name)[0] + '.pdf'
                job = ProcessingJob.objects.create(
                    user=request.user if request.user.is_authenticated else None,
                    tool_name='sign_pdf',
                    original_filename=pdf_file.name,
                    status='COMPLETED',
                    completed_at=timezone.now(),
                    output_file=output_path,
                    output_filename=output_filename,
                )
                try:
                    os.remove(pdf_path)
                except OSError:
                    pass
                return redirect(reverse('download_file', args=[job.id]))
            except SignatureError as e:
                messages.error(request, str(e))
            except ValueError as e:
                messages.error(request, str(e))
            except Exception:
                messages.error(request, "Something went wrong while signing the PDF")
            finally:
                try:
                    os.remove(pdf_path)
                except OSError:
                    pass
    return render(request, 'pdf_tools/security/sign.html',
                  {'form': upload_form, 'config_form': sig_form,
                   'tool_name': 'Sign PDF', 'submit_label': 'Sign PDF'})


# --------------------------------------------------------------------------- #
# PDF Optimize / Repair views
# --------------------------------------------------------------------------- #

def repair_pdf(request):
    return _handle_pdf_config_tool(
        request, 'repair_pdf', 'Repair PDF', Form, _repair_pdf,
        '.pdf', 'pdf_tools/config_form.html', needs_config=False)


# --------------------------------------------------------------------------- #
# PDF OCR views
# --------------------------------------------------------------------------- #

def ocr_pdf_view(request):
    return _handle_pdf_config_tool(
        request, 'ocr_pdf', 'OCR PDF', OcrForm, ocr_pdf,
        '.pdf', 'pdf_tools/config_form.html')


def scan_to_pdf(request):
    """Scan/image to searchable PDF. Upload images, convert to PDF, then OCR."""
    form = ImageUploadAnyForm(data=request.POST, files=request.FILES) if request.method == 'POST' else ImageUploadAnyForm()
    if request.method == 'POST' and form.is_valid():
        files = request.FILES.getlist('files')
        if not files:
            messages.error(request, "Please upload at least one image")
            return render(request, 'pdf_tools/image_upload.html',
                          {'form': form, 'tool_name': 'Scan to Searchable PDF',
                           'upload_icon': '📸', 'drop_text': 'Drop your images here',
                           'hint_text': 'JPG, PNG, WebP supported',
                           'submit_label': 'Scan to Searchable PDF'})
        file_paths = []
        for f in files:
            valid, err = validate_image_any(f)
            if not valid:
                messages.error(request, err)
                return render(request, 'pdf_tools/image_upload.html',
                              {'form': form, 'tool_name': 'Scan to Searchable PDF',
                               'upload_icon': '📸', 'drop_text': 'Drop your images here',
                               'hint_text': 'JPG, PNG, WebP supported',
                               'submit_label': 'Scan to Searchable PDF'})
            file_paths.append(save_uploaded_file(f))
        try:
            temp_pdf = _image_to_pdf(file_paths)
            if not tesseract_available():
                messages.error(request, "OCR is not available on this server. Install Tesseract to use this feature.")
                try:
                    os.remove(temp_pdf)
                except OSError:
                    pass
                return render(request, 'pdf_tools/image_upload.html',
                              {'form': form, 'tool_name': 'Scan to Searchable PDF',
                               'upload_icon': '📸', 'drop_text': 'Drop your images here',
                               'hint_text': 'JPG, PNG, WebP supported',
                               'submit_label': 'Scan to Searchable PDF'})
            output_path = ocr_pdf(temp_pdf, {'pages': '', 'lang': 'eng'})
            output_filename = os.path.splitext(files[0].name)[0] + '.pdf'
            job = ProcessingJob.objects.create(
                user=request.user if request.user.is_authenticated else None,
                tool_name='scan_to_pdf',
                original_filename=files[0].name,
                status='COMPLETED',
                completed_at=timezone.now(),
                output_file=output_path,
                output_filename=output_filename,
            )
            for p in file_paths:
                try:
                    os.remove(p)
                except OSError:
                    pass
            return redirect(reverse('download_file', args=[job.id]))
        except OCRNotConfiguredError as e:
            messages.error(request, str(e))
        except Exception:
            messages.error(request, "Something went wrong while scanning to searchable PDF")
        finally:
            for p in file_paths:
                try:
                    os.remove(p)
                except OSError:
                    pass
    return render(request, 'pdf_tools/image_upload.html',
                  {'form': form, 'tool_name': 'Scan to Searchable PDF',
                   'upload_icon': '📸', 'drop_text': 'Drop your images here',
                   'hint_text': 'JPG, PNG, WebP supported',
                   'submit_label': 'Scan to Searchable PDF'})