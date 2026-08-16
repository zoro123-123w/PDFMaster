"""PDF AI services: text extraction, summarisation, translation, Q&A.

All AI calls go through :mod:`ai_tools.services.ai_provider` so that the
API key and model are driven entirely by environment variables. When no
AI key is configured the tools degrade gracefully – extraction and
keyword-based fallback still work for non-AI use.
"""
import logging

from django.conf import settings
from pypdf import PdfReader
import pymupdf

from .ai_provider import AIServiceError, call_ai, truncate_text, MAX_PROMPT_CHARS

logger = logging.getLogger(__name__)

MAX_CONTEXT_CHARS = 8000
SUMMARIZE_SYSTEM = (
    'You are a helpful AI assistant that summarises documents. '
    'Produce a concise, well-structured summary that captures the main '
    'points and key takeaways. Use clear section headings.'
)
TRANSLATE_SYSTEM = (
    'You are a professional translator. Translate the provided text '
    'accurately into the requested language, preserving meaning, tone '
    'and formatting.'
)
ANSWER_SYSTEM = (
    'You are a helpful assistant that answers questions based on the '
    'provided document text. If the answer cannot be found in the text, '
    'say so clearly.'
)

MIN_TEXT_LENGTH = 50


class ExtractionError(ValueError):
    """Raised when no sufficient text can be extracted from a PDF."""
    pass


def get_ai_config():
    """Return AI provider configuration read from Django settings.

    The API key is taken from the environment via settings (never hardcoded)
    so the same code works on localhost and on Render.
    """
    return {
        'provider': getattr(settings, 'AI_PROVIDER', 'openai'),
        'api_key': bool(getattr(settings, 'AI_API_KEY', '')),
        'model': getattr(settings, 'AI_DEFAULT_MODEL', 'gpt-4o-mini'),
        'base_url': getattr(settings, 'AI_BASE_URL', ''),
    }


def _extract_with_pypdf(file_path):
    reader = PdfReader(file_path)
    try:
        text = ""
        for page in reader.pages:
            page_text = page.extract_text() or ""
            text += page_text
        return text.strip()
    finally:
        try:
            reader.stream.close()
        except Exception:
            pass


def _extract_with_fitz(file_path):
    doc = pymupdf.open(file_path)
    try:
        text = ""
        for page in doc:
            text += page.get_text()
        return text.strip()
    finally:
        doc.close()


def extract_text_from_pdf(file_path):
    """Extract all text from a PDF, trying pypdf first then PyMuPDF.

    Raises :class:`ExtractionError` when the extracted text is empty or
    shorter than ``MIN_TEXT_LENGTH`` characters – this usually means the
    PDF is a scanned image rather than a text-based document.
    """
    text = ""
    try:
        text = _extract_with_pypdf(file_path)
        if text:
            pass
    except Exception as exc:
        logger.debug('pypdf extraction failed: %s', exc)

    if not text:
        try:
            text = _extract_with_fitz(file_path)
        except Exception as exc:
            logger.debug('pymupdf extraction failed: %s', exc)

    text = text.strip()
    if len(text) < MIN_TEXT_LENGTH:
        raise ExtractionError(
            'Could not extract text from this PDF. Please ensure it is a '
            'text-based document and not a scanned image. For scanned PDFs, '
            'use the OCR tool first (Tools -> OCR PDF).'
        )
    return text


def chunk_text(text, max_chars=MAX_CONTEXT_CHARS):
    """Split text into chunks of roughly max_chars, breaking on newlines."""
    if len(text) <= max_chars:
        return [text]
    chunks = []
    current = []
    current_len = 0
    for line in text.splitlines():
        if current_len + len(line) + 1 > max_chars and current:
            chunks.append('\n'.join(current))
            current = []
            current_len = 0
        current.append(line)
        current_len += len(line) + 1
    if current:
        chunks.append('\n'.join(current))
    return chunks


def summarize_pdf(file_path):
    """Extract text from PDF and generate an abstractive summary via AI.

    Falls back to returning the extracted text when no AI key is configured.
    """
    text = extract_text_from_pdf(file_path)
    config = get_ai_config()
    if config['api_key']:
        try:
            chunks = chunk_text(text)
            combined = []
            for i, chunk in enumerate(chunks):
                if len(chunks) > 1:
                    user_prompt = f"Document part {i+1} of {len(chunks)}:\n\n{chunk}"
                else:
                    user_prompt = chunk
                summary_part = call_ai(SUMMARIZE_SYSTEM, user_prompt,
                                        max_tokens=1500, temperature=0.5)
                combined.append(summary_part)
            if len(combined) > 1:
                overall = call_ai(
                    SUMMARIZE_SYSTEM,
                    'Summarise the following collection of partial summaries into one '
                    'concise document summary:\n\n' + '\n\n'.join(combined),
                    max_tokens=1500, temperature=0.5)
                return overall.strip()
            return combined[0].strip()
        except AIServiceError:
            return text
    return text


def translate_text(text, target_language="english"):
    """Translate text into the requested language using the configured AI provider.

    Falls back to returning the original text when no AI key is configured.
    """
    if not text:
        return ""

    config = get_ai_config()
    if config['api_key']:
        try:
            user_prompt = f"Translate the following text to {target_language}:\n\n{truncate_text(text, 4000)}"
            result = call_ai(TRANSLATE_SYSTEM, user_prompt,
                             max_tokens=4000, temperature=0.3)
            return result.strip()
        except AIServiceError:
            return f"[Translation to {target_language} – AI service unavailable]\n\n{text}"
    return f"[Translation to {target_language} – API key not configured]\n\n{text}"


def answer_question(text, question):
    """Answer a question about the provided PDF text using the AI provider.

    Falls back to keyword matching when no AI key is configured.
    """
    if not text:
        raise ValueError("No text available to answer the question.")
    if not question:
        raise ValueError("A question is required.")

    config = get_ai_config()
    if config['api_key']:
        try:
            prompt = (
                f"Document text:\n\n{truncate_text(text, MAX_CONTEXT_CHARS)}\n\n"
                f"Question: {question}\n\nAnswer:"
            )
            result = call_ai(ANSWER_SYSTEM, prompt,
                             max_tokens=2000, temperature=0.5)
            return result.strip()
        except AIServiceError:
            return _keyword_answer(text, question)
    return _keyword_answer(text, question)


def _keyword_answer(text, question):
    """Simple keyword-matching fallback when the AI provider is unavailable."""
    keywords = question.lower().split()
    relevant_sentences = []
    sentences = text.split('.')
    for sentence in sentences:
        if any(kw in sentence.lower() for kw in keywords):
            relevant_sentences.append(sentence.strip())
    if relevant_sentences:
        return ". ".join(relevant_sentences) + "."
    return "No relevant information found in the document."
