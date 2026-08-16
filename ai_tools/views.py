import os
import json
import logging

from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.utils import timezone

from .models import AIRequest
from .forms import AIUploadForm, TranslationForm, QuizForm, FlashcardForm, StudyForm, QuestionBankForm
from .services.pdf_ai import (
    extract_text_from_pdf, summarize_pdf, translate_text, answer_question,
    ExtractionError,
)
from .services.study_ai import (
    generate_quiz, generate_flashcards, generate_study_notes, generate_study_guide,
    generate_question_bank, identify_important_questions, generate_chapter_summary,
    extract_key_concepts, generate_exam_prep,
)
from .services.ai_provider import AIServiceError, MAX_PROMPT_CHARS
from pdf_tools.views import validate_pdf, save_uploaded_file

logger = logging.getLogger(__name__)

AI_TOOLS = [
    {'name': 'Summarize PDF', 'url': 'ai_summarize', 'description': 'Get a concise summary of your PDF document', 'icon': '🧠'},
    {'name': 'Extract Text', 'url': 'ai_extract', 'description': 'Extract all text content from a PDF', 'icon': '📝'},
    {'name': 'Translate Text', 'url': 'ai_translate', 'description': 'Translate text into another language', 'icon': '🌐'},
    {'name': 'Ask Question', 'url': 'ai_ask', 'description': 'Ask a question about your PDF and get an answer', 'icon': '❓'},
]

AI_STUDY_TOOLS = [
    {'name': 'AI Quiz Generator', 'url': 'ai_study_quiz', 'description': 'Generate multiple-choice quizzes from your PDF', 'icon': '📝'},
    {'name': 'Flashcard Generator', 'url': 'ai_study_flashcards', 'description': 'Create question-answer flashcards with next/prev controls', 'icon': '🃏'},
    {'name': 'Study Notes', 'url': 'ai_study_notes', 'description': 'Generate structured study notes with headings and bullets', 'icon': '📋'},
    {'name': 'Study Guide', 'url': 'ai_study_guide', 'description': 'Complete study plan with key topics and revision sections', 'icon': '📚'},
    {'name': 'Question Bank', 'url': 'ai_study_questions', 'description': 'Generate short, long, and conceptual questions', 'icon': '🏦'},
    {'name': 'Important Questions', 'url': 'ai_study_important', 'description': 'Identify likely important questions from your material', 'icon': '⭐'},
    {'name': 'Chapter Summary', 'url': 'ai_study_chapters', 'description': 'Concise chapter-wise summaries and key points', 'icon': '📖'},
    {'name': 'Key Concepts', 'url': 'ai_study_concepts', 'description': 'Extract concepts, definitions, and explanations', 'icon': '💡'},
    {'name': 'Exam Preparation', 'url': 'ai_study_exam', 'description': 'Revision material, practice questions, and quick notes', 'icon': '🎓'},
]


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _is_ajax(request):
    return request.headers.get('X-Requested-With') == 'XMLHttpRequest'


def _first_form_error(form):
    """Extract the first human-readable error message from a Django form."""
    errors = form.errors.get_json_data()
    for field_errors in errors.values():
        if field_errors:
            return field_errors[0]['message']
    return 'Invalid form data.'


def _json_error(message, status=400):
    """Return a JsonResponse error suitable for AJAX callers."""
    return JsonResponse({'error': message}, status=status)


def _json_success(response_text, job_id, tool_label):
    """Return a JsonResponse with the AI result for AJAX callers."""
    return JsonResponse({
        'result': response_text,
        'job_id': str(job_id),
        'tool_label': tool_label,
    })


def _create_ai_job(request, tool_key, prompt, response_text):
    """Create and return an AIRequest record."""
    return AIRequest.objects.create(
        user=request.user if request.user.is_authenticated else None,
        tool=tool_key,
        prompt=prompt,
        response=response_text,
        status='COMPLETED',
        completed_at=timezone.now(),
    )


def _safe_remove(file_path):
    try:
        os.remove(file_path)
    except OSError:
        pass


# --------------------------------------------------------------------------- #
# Page listing views
# --------------------------------------------------------------------------- #

def ai_tools_list(request):
    return render(request, 'ai_tools/ai_tools.html', {
        'ai_tools': AI_TOOLS,
        'ai_study_tools': AI_STUDY_TOOLS,
    })


def ai_study_list(request):
    return render(request, 'ai_tools/ai_study.html', {
        'ai_study_tools': AI_STUDY_TOOLS,
    })


# --------------------------------------------------------------------------- #
# PDF-based AI tools (summarize / extract / ask)
# --------------------------------------------------------------------------- #

def _handle_pdf_tool(request, tool_key, tool_label, service_fn, needs_question):
    """Shared handler for the PDF-based AI tools (summarize / extract / ask).

    For AJAX: returns JsonResponse with result or error.
    For regular form posts: creates a job and redirects to detail page.
    """
    ajax = _is_ajax(request)
    form_kwargs = {'data': request.POST, 'files': request.FILES} if request.method == 'POST' else {}
    form = AIUploadForm(**form_kwargs)

    if request.method == 'POST':
        # Explicit file presence check before form validation
        f = request.FILES.get('file')
        if not f:
            msg = 'No file uploaded or text extracted.'
            if ajax:
                return _json_error(msg, 400)
            messages.error(request, 'Please upload a PDF file before proceeding.')
            return render(request, 'ai_tools/ai_form.html', {
                'form': form, 'tool_name': tool_label, 'question': needs_question,
            })

        question = (form.cleaned_data.get('question') or '').strip() if form.is_valid() else ''
        if needs_question and not question:
            if ajax:
                return _json_error('Please enter your question.', 400)
            form.add_error('question', 'Please enter your question.')
            return render(request, 'ai_tools/ai_form.html', {
                'form': form, 'tool_name': tool_label, 'question': needs_question,
            })

        valid, err = validate_pdf(f)
        if not valid:
            if ajax:
                return _json_error(err, 400)
            messages.error(request, err)
            return render(request, 'ai_tools/ai_form.html', {
                'form': form, 'tool_name': tool_label, 'question': needs_question,
            })

        file_path = save_uploaded_file(f)
        try:
            prompt_text = question if needs_question else ''
            response_text = service_fn(file_path, question)
            job = _create_ai_job(request, tool_key, prompt_text, response_text)
            if ajax:
                return _json_success(response_text, job.id, tool_label)
            return redirect('ai_request_detail', job.id)
        except ExtractionError as e:
            logger.error('Text extraction failed for %s: %s', tool_key, e)
            if ajax:
                return _json_error(str(e), 400)
            messages.error(request, str(e))
        except AIServiceError as e:
            logger.error('AI service error in %s: %s', tool_key, e)
            if ajax:
                return _json_error(str(e), 502)
            messages.error(request, str(e))
        except Exception:
            logger.exception('Unexpected error in %s', tool_key)
            if ajax:
                return _json_error('Something went wrong while processing your request.', 500)
            messages.error(request, 'Something went wrong while processing your PDF')
        finally:
            _safe_remove(file_path)

    return render(request, 'ai_tools/ai_form.html', {
        'form': form, 'tool_name': tool_label, 'question': needs_question,
    })


def summarize_pdf_view(request):
    return _handle_pdf_tool(
        request, 'summarize', 'Summarize PDF', lambda fp, q: summarize_pdf(fp), False)


def extract_text_view(request):
    return _handle_pdf_tool(
        request, 'extract', 'Extract Text', lambda fp, q: extract_text_from_pdf(fp), False)


def ask_question_view(request):
    return _handle_pdf_tool(
        request, 'ask', 'Ask Question',
        lambda fp, q: answer_question(extract_text_from_pdf(fp), q), True)


def translate_text_view(request):
    ajax = _is_ajax(request)
    if request.method == 'POST':
        form = TranslationForm(request.POST)
        if form.is_valid():
            text = form.cleaned_data['text']
            target = form.cleaned_data['target_language']
            if not text or not text.strip():
                if ajax:
                    return _json_error('Please provide text to translate.', 400)
                messages.error(request, 'Please provide text to translate.')
                return render(request, 'ai_tools/translate.html', {'form': form})
            try:
                response_text = translate_text(text, target)
                job = _create_ai_job(request, 'translate', text, response_text)
                if ajax:
                    return _json_success(response_text, job.id, 'Translate Text')
                return redirect('ai_request_detail', job.id)
            except AIServiceError as e:
                logger.error('AI service error in translate: %s', e)
                if ajax:
                    return _json_error(str(e), 502)
                messages.error(request, str(e))
            except Exception:
                logger.exception('Unexpected error in translate')
                if ajax:
                    return _json_error('Something went wrong while translating.', 500)
                messages.error(request, 'Something went wrong while translating')
        else:
            if ajax:
                first_error = _first_form_error(form)
                return _json_error(first_error, 400)
    else:
        form = TranslationForm()
    return render(request, 'ai_tools/translate.html', {'form': form})


# --------------------------------------------------------------------------- #
# AI result detail / download views
# --------------------------------------------------------------------------- #

def ai_request_detail(request, request_id):
    try:
        job = AIRequest.objects.get(id=request_id)
    except AIRequest.DoesNotExist:
        messages.error(request, 'Request not found')
        return redirect('ai_tools')
    tool_label = dict(AIRequest.TOOL_CHOICES).get(job.tool, job.tool)

    if job.tool == 'quiz':
        try:
            data = json.loads(job.response or '{}')
        except (json.JSONDecodeError, TypeError):
            data = {}
        return render(request, 'ai_tools/quiz_result.html', {
            'job': job, 'tool_label': tool_label, 'quiz_data': data,
        })
    if job.tool == 'flashcards':
        try:
            data = json.loads(job.response or '{}')
        except (json.JSONDecodeError, TypeError):
            data = {}
        flashcards_json = '[]'
        if data:
            flashcards_json = json.dumps(data.get('flashcards', []))
        return render(request, 'ai_tools/flashcard_result.html', {
            'job': job, 'tool_label': tool_label, 'flashcard_data': data,
            'flashcards_json': flashcards_json,
        })
    return render(request, 'ai_tools/result.html', {'job': job, 'tool_label': tool_label})


def download_ai_result(request, request_id):
    try:
        job = AIRequest.objects.get(id=request_id)
    except AIRequest.DoesNotExist:
        messages.error(request, 'Request not found')
        return redirect('ai_tools')
    if job.tool in ('quiz', 'flashcards'):
        content_type = 'application/json; charset=utf-8'
        ext = 'json'
    else:
        content_type = 'text/plain; charset=utf-8'
        ext = 'txt'
    response = HttpResponse(job.response or '', content_type=content_type)
    filename = job.get_tool_display().replace(' ', '_') + '_result.' + ext
    response['Content-Disposition'] = 'attachment; filename="' + filename + '"'
    return response


# --------------------------------------------------------------------------- #
# AI Study Suite shared handlers
# --------------------------------------------------------------------------- #

def _process_study_post(request, form, tool_key, tool_label, service_fn,
                        template='ai_tools/study_form.html'):
    """Shared POST-handler for study tools returning a text response.

    For AJAX: returns JsonResponse with the result text.
    For regular form posts: creates a job and redirects to detail page.
    """
    ajax = _is_ajax(request)

    f = request.FILES.get('file')
    if not f:
        msg = 'No file uploaded or text extracted.'
        if ajax:
            return _json_error(msg, 400)
        messages.error(request, 'Please upload a PDF file before proceeding.')
        return render(request, template, {'form': form, 'tool_name': tool_label})

    valid, err = validate_pdf(f)
    if not valid:
        if ajax:
            return _json_error(err, 400)
        messages.error(request, err)
        return render(request, template, {'form': form, 'tool_name': tool_label})

    file_path = save_uploaded_file(f)
    try:
        extra = (form.cleaned_data.get('extra') or '').strip() if form.is_bound else ''
        response_text = service_fn(file_path, extra) if extra else service_fn(file_path)
        job = _create_ai_job(request, tool_key, extra, response_text)
        if ajax:
            return _json_success(response_text, job.id, tool_label)
        return redirect('ai_request_detail', job.id)
    except ExtractionError as e:
        logger.error('Text extraction failed for %s: %s', tool_key, e)
        if ajax:
            return _json_error(str(e), 400)
        messages.error(request, str(e))
    except AIServiceError as e:
        logger.error('AI service error in %s: %s', tool_key, e)
        if ajax:
            return _json_error(str(e), 502)
        messages.error(request, str(e))
    except Exception:
        logger.exception('Unexpected error in %s', tool_key)
        if ajax:
            return _json_error('Something went wrong while generating study material.', 500)
        messages.error(request, 'Something went wrong while generating study material')
    finally:
        _safe_remove(file_path)
    return render(request, template, {'form': form, 'tool_name': tool_label})


def _handle_study_tool(request, tool_key, tool_label, form_class, service_fn,
                       template='ai_tools/study_form.html'):
    """Shared handler for study tools that return a text response."""
    ajax = _is_ajax(request)
    form_kwargs = {'data': request.POST, 'files': request.FILES} if request.method == 'POST' else {}
    form = form_class(**form_kwargs)

    if request.method == 'POST':
        # Check file presence early for AJAX callers
        if not request.FILES.get('file'):
            msg = 'No file uploaded or text extracted.'
            if ajax:
                return _json_error(msg, 400)
            messages.error(request, 'Please upload a PDF file before proceeding.')
            return render(request, template, {'form': form, 'tool_name': tool_label})

        if form.is_valid():
            return _process_study_post(request, form, tool_key, tool_label,
                                       service_fn, template)
        if ajax:
            first_error = _first_form_error(form)
            return _json_error(first_error, 400)
    return render(request, template, {'form': form, 'tool_name': tool_label})


def _process_study_special(request, form, tool_key, tool_label,
                           service_fn, extra_prompt='',
                           template='ai_tools/study_form.html'):
    """Shared POST-handler for study tools that produce structured JSON
    (quiz / flashcards / question bank).

    For AJAX: returns JsonResponse with the JSON result text.
    For regular form posts: creates a job and redirects to detail page.
    """
    ajax = _is_ajax(request)

    f = request.FILES.get('file')
    if not f:
        msg = 'No file uploaded or text extracted.'
        if ajax:
            return _json_error(msg, 400)
        messages.error(request, 'Please upload a PDF file before proceeding.')
        return render(request, template, {'form': form, 'tool_name': tool_label})

    valid, err = validate_pdf(f)
    if not valid:
        if ajax:
            return _json_error(err, 400)
        messages.error(request, err)
        return render(request, template, {'form': form, 'tool_name': tool_label})

    file_path = save_uploaded_file(f)
    try:
        response_text = service_fn(file_path)
        job = _create_ai_job(request, tool_key, extra_prompt, response_text)
        if ajax:
            return _json_success(response_text, job.id, tool_label)
        return redirect('ai_request_detail', job.id)
    except ExtractionError as e:
        logger.error('Text extraction failed for %s: %s', tool_key, e)
        if ajax:
            return _json_error(str(e), 400)
        messages.error(request, str(e))
    except AIServiceError as e:
        logger.error('AI service error in %s: %s', tool_key, e)
        if ajax:
            return _json_error(str(e), 502)
        messages.error(request, str(e))
    except Exception:
        logger.exception('Unexpected error in %s', tool_key)
        if ajax:
            return _json_error('Something went wrong while generating study material.', 500)
        messages.error(request, 'Something went wrong while generating study material')
    finally:
        _safe_remove(file_path)
    return render(request, template, {'form': form, 'tool_name': tool_label})


# --------------------------------------------------------------------------- #
# Individual study tool views
# --------------------------------------------------------------------------- #

def quiz_view(request):
    """AI Quiz Generator – produces structured JSON for the quiz template."""
    form = QuizForm(data=request.POST, files=request.FILES) if request.method == 'POST' else QuizForm()
    if request.method == 'POST':
        if form.is_valid():
            num = form.cleaned_data.get('num_questions') or 10
            difficulty = form.cleaned_data.get('difficulty') or 'medium'

            def _svc(file_path):
                result = generate_quiz(file_path, num_questions=num, difficulty=difficulty)
                return json.dumps(result)

            return _process_study_special(
                request, form, 'quiz', 'AI Quiz Generator',
                _svc,
                extra_prompt=f'{num} questions, difficulty={difficulty}')
        if _is_ajax(request):
            first_error = _first_form_error(form)
            return _json_error(first_error, 400)
    return render(request, 'ai_tools/study_form.html', {'form': form, 'tool_name': 'AI Quiz Generator'})


def flashcards_view(request):
    """Flashcard Generator – produces structured JSON for the flashcard template."""
    form = FlashcardForm(data=request.POST, files=request.FILES) if request.method == 'POST' else FlashcardForm()
    if request.method == 'POST':
        if form.is_valid():
            num = form.cleaned_data.get('num_flashcards') or 15

            def _svc(file_path):
                result = generate_flashcards(file_path, num_flashcards=num)
                return json.dumps(result)

            return _process_study_special(
                request, form, 'flashcards', 'Flashcard Generator',
                _svc,
                extra_prompt=f'{num} flashcards')
        if _is_ajax(request):
            first_error = _first_form_error(form)
            return _json_error(first_error, 400)
    return render(request, 'ai_tools/study_form.html', {'form': form, 'tool_name': 'Flashcard Generator'})


def study_notes_view(request):
    return _handle_study_tool(
        request, 'study_notes', 'Study Notes', StudyForm,
        generate_study_notes)


def study_guide_view(request):
    return _handle_study_tool(
        request, 'study_guide', 'Study Guide', StudyForm,
        generate_study_guide)


def question_bank_view(request):
    """Question Bank – configurable number of questions per type."""
    form = QuestionBankForm(data=request.POST, files=request.FILES) if request.method == 'POST' else QuestionBankForm()
    if request.method == 'POST':
        if form.is_valid():
            num = form.cleaned_data.get('num_questions') or 20

            def _svc(file_path):
                return generate_question_bank(file_path, num_questions=num)

            return _process_study_special(
                request, form, 'question_bank', 'Question Bank Generator',
                _svc,
                extra_prompt=f'{num} questions per type')
        if _is_ajax(request):
            first_error = _first_form_error(form)
            return _json_error(first_error, 400)
    return render(request, 'ai_tools/study_form.html', {'form': form, 'tool_name': 'Question Bank Generator'})


def important_questions_view(request):
    return _handle_study_tool(
        request, 'important_questions', 'Important Questions', StudyForm,
        identify_important_questions)


def chapter_summary_view(request):
    return _handle_study_tool(
        request, 'chapter_summary', 'Chapter Summary', StudyForm,
        generate_chapter_summary)


def key_concepts_view(request):
    return _handle_study_tool(
        request, 'key_concepts', 'Key Concepts', StudyForm,
        extract_key_concepts)


def exam_prep_view(request):
    return _handle_study_tool(
        request, 'exam_prep', 'Exam Preparation', StudyForm,
        generate_exam_prep)
