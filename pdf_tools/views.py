import os
import uuid
from django.conf import settings
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse, FileResponse
from django.urls import reverse
from django.utils import timezone
from .models import ProcessingJob
from .forms import PDFUploadForm, SinglePDFUploadForm, ImageUploadForm, PageRangeForm, RotationForm
from .services.merge import merge_pdf_service
from .services.split import split_pdf_service
from .services.compress import compress_pdf_service
from .services.jpg_to_pdf import jpg_to_pdf_service
from .services.pdf_to_jpg import pdf_to_jpg_service
from .services.rotate import rotate_pdf_service
from .services.delete_pages import delete_pages_service
from .services.extract_pages import extract_pages_service


def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    return x_forwarded_for.split(',')[0] if x_forwarded_for else request.META.get('REMOTE_ADDR')


def validate_pdf(file_obj):
    if file_obj.size > settings.MAX_UPLOAD_SIZE:
        return False, f"File exceeds maximum size of {settings.MAX_UPLOAD_SIZE // (1024*1024)} MB"
    if not file_obj.name.lower().endswith('.pdf'):
        return False, "File is not a PDF"
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


def tools_list(request):
    tools = [
        {'name': 'Merge PDF', 'url': 'merge_pdf', 'description': 'Combine multiple PDFs into one document', 'icon': '📄'},
        {'name': 'Split PDF', 'url': 'split_pdf', 'description': 'Extract pages or ranges from a PDF', 'icon': '✂️'},
        {'name': 'Compress PDF', 'url': 'compress_pdf', 'description': 'Reduce PDF file size while preserving quality', 'icon': '🗜️'},
        {'name': 'JPG to PDF', 'url': 'jpg_to_pdf', 'description': 'Convert JPG/PNG images to PDF', 'icon': '🖼️'},
        {'name': 'PDF to JPG', 'url': 'pdf_to_jpg', 'description': 'Convert PDF pages to JPG images', 'icon': '📷'},
        {'name': 'Rotate PDF', 'url': 'rotate_pdf', 'description': 'Rotate PDF pages by 90, 180, or 270 degrees', 'icon': '🔄'},
        {'name': 'Delete PDF Pages', 'url': 'delete_pages', 'description': 'Remove specific pages from a PDF', 'icon': '🗑️'},
        {'name': 'Extract PDF Pages', 'url': 'extract_pages', 'description': 'Extract selected pages to a new PDF', 'icon': '📑'},
    ]
    return render(request, 'tools.html', {'tools': tools})


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
        response = FileResponse(open(job.output_file, 'rb'), as_attachment=True, filename=os.path.basename(job.output_file))
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