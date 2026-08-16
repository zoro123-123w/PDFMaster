"""AI Study Suite services.

Each function extracts text from a PDF (chunking intelligently for long
documents) and asks the configured AI provider to produce study material.

Structured outputs (quiz, flashcards, question bank) ask the provider to
return JSON so the result can be rendered nicely.

When no AI API key is configured the provider layer raises
:class:`AIServiceError` and each study function returns a friendly message
so the application never crashes.
"""
import json

from .ai_provider import AIServiceError, call_ai, truncate_text, safe_truncate, MAX_PROMPT_CHARS
from .pdf_ai import extract_text_from_pdf, chunk_text, MAX_CONTEXT_CHARS

# --------------------------------------------------------------------------- #
# System prompts
# --------------------------------------------------------------------------- #

_STUDY_SYSTEM = (
    'You are an expert AI tutor. You generate high-quality study materials '
    'from the provided source text. All content you produce must be based '
    'directly on the source text – do not invent facts.'
)


def _extract_for_study(file_path):
    """Extract and safely truncate PDF text suitable for a single AI call.

    Uses :func:`safe_truncate` to cap at ``MAX_PROMPT_CHARS`` (20 000) so that
    Groq / OpenAI-compatible providers do not reject the request with a 400
    for exceeding the context window.
    """
    text = extract_text_from_pdf(file_path)
    return safe_truncate(text, MAX_PROMPT_CHARS)


def _study_call(user_prompt, max_tokens=4000, temperature=0.7):
    return call_ai(_STUDY_SYSTEM, user_prompt,
                   max_tokens=max_tokens, temperature=temperature)


# --------------------------------------------------------------------------- #
# 1. Quiz Generator
# --------------------------------------------------------------------------- #

def generate_quiz(file_path, num_questions=10, difficulty='medium'):
    text = _extract_for_study(file_path)
    prompt = (
        f'Create a multiple-choice quiz with {num_questions} questions at '
        f'{difficulty} difficulty based on the following document.\n\n'
        f'Return ONLY valid JSON in this exact format:\n'
        f'{{"questions": [{{"question": "...", "options": ["a","b","c","d"], '
        f'"answer": "a", "explanation": "..."}}]}}\n\n'
        f'Document:\n{text}'
    )
    raw = _study_call(prompt, max_tokens=6000, temperature=0.6)
    try:
        data = json.loads(raw)
        questions = data.get('questions', [])
        return {'questions': questions}
    except (json.JSONDecodeError, AttributeError):
        # If the AI didn't return clean JSON, parse what we can.
        return {'questions': [], 'raw': raw}


# --------------------------------------------------------------------------- #
# 2. Flashcard Generator
# --------------------------------------------------------------------------- #

def generate_flashcards(file_path, num_flashcards=15):
    text = _extract_for_study(file_path)
    prompt = (
        f'Create {num_flashcards} question-answer flashcards based on the '
        f'following document. Each flashcard should test understanding of '
        f'a key concept, fact, or term.\n\n'
        f'Return ONLY valid JSON in this exact format:\n'
        f'{{"flashcards": [{{"front": "...", "back": "..."}}]}}\n\n'
        f'Document:\n{text}'
    )
    raw = _study_call(prompt, max_tokens=6000, temperature=0.6)
    try:
        data = json.loads(raw)
        return {'flashcards': data.get('flashcards', [])}
    except (json.JSONDecodeError, AttributeError):
        return {'flashcards': [], 'raw': raw}


# --------------------------------------------------------------------------- #
# 3. Study Notes Generator
# --------------------------------------------------------------------------- #

def generate_study_notes(file_path, extra=None):
    text = _extract_for_study(file_path)
    extra_str = f'\n\nAdditional instructions:\n{extra}' if extra else ''
    prompt = (
        f'Generate well-structured study notes from the following document. '
        f'Use clear headings, bullet points, and highlight important concepts.'
        f'{extra_str}\n\nDocument:\n{text}'
    )
    return _study_call(prompt, max_tokens=6000, temperature=0.5)


# --------------------------------------------------------------------------- #
# 4. Study Guide Generator
# --------------------------------------------------------------------------- #

def generate_study_guide(file_path, extra=None):
    text = _extract_for_study(file_path)
    extra_str = f'\n\nAdditional instructions:\n{extra}' if extra else ''
    prompt = (
        f'Create a comprehensive study guide from the following document. '
        f'Include: key topics, important definitions, core concepts, '
        f'detailed explanations with examples, and revision sections.'
        f'{extra_str}\n\nDocument:\n{text}'
    )
    return _study_call(prompt, max_tokens=8000, temperature=0.5)


# --------------------------------------------------------------------------- #
# 5. Question Bank Generator
# --------------------------------------------------------------------------- #

def generate_question_bank(file_path, num_questions=20):
    text = _extract_for_study(file_path)
    prompt = (
        f'Generate a question bank from the following document with '
        f'{num_questions} questions of each type: short questions, long '
        f'questions, and conceptual questions. Return as formatted text with '
        f'clear sections and numbered questions. All questions must be '
        f'supported by the document.\n\nDocument:\n{text}'
    )
    return _study_call(prompt, max_tokens=8000, temperature=0.6)


# --------------------------------------------------------------------------- #
# 6. Important Questions
# --------------------------------------------------------------------------- #

def identify_important_questions(file_path, extra=None):
    text = _extract_for_study(file_path)
    extra_str = f'\n\nAdditional instructions:\n{extra}' if extra else ''
    prompt = (
        f'Identify the most important questions and topics that a student '
        f'should focus on from the following document. List them with brief '
        f'explanations of why each is important.'
        f'{extra_str}\n\nDocument:\n{text}'
    )
    return _study_call(prompt, max_tokens=6000, temperature=0.5)


# --------------------------------------------------------------------------- #
# 7. Chapter Summary
# --------------------------------------------------------------------------- #

def generate_chapter_summary(file_path, extra=None):
    text = _extract_for_study(file_path)
    extra_str = f'\n\nAdditional instructions:\n{extra}' if extra else ''
    prompt = (
        f'Generate a concise chapter-wise summary of the following document. '
        f'For each section/chapter, list the key points and main takeaways.'
        f'{extra_str}\n\nDocument:\n{text}'
    )
    return _study_call(prompt, max_tokens=6000, temperature=0.5)


# --------------------------------------------------------------------------- #
# 8. Key Concepts
# --------------------------------------------------------------------------- #

def extract_key_concepts(file_path, extra=None):
    text = _extract_for_study(file_path)
    extra_str = f'\n\nAdditional instructions:\n{extra}' if extra else ''
    prompt = (
        f'Extract the key concepts, definitions, and explanations from the '
        f'following document. For each concept, provide a clear definition '
        f'and, when supported by the source text, an example.'
        f'{extra_str}\n\nDocument:\n{text}'
    )
    return _study_call(prompt, max_tokens=6000, temperature=0.5)


# --------------------------------------------------------------------------- #
# 9. Exam Preparation
# --------------------------------------------------------------------------- #

def generate_exam_prep(file_path, extra=None):
    text = _extract_for_study(file_path)
    extra_str = f'\n\nAdditional instructions:\n{extra}' if extra else ''
    prompt = (
        f'Generate exam preparation material from the following document. '
        f'Include: a list of important topics to focus on, practice '
        f'questions, quick revision notes, and key formulas or definitions.'
        f'{extra_str}\n\nDocument:\n{text}'
    )
    return _study_call(prompt, max_tokens=8000, temperature=0.5)
