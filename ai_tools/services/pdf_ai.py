import os
import uuid
from pypdf import PdfReader
import pymupdf


def extract_text_from_pdf(file_path):
    """Extract text content from a PDF file."""
    try:
        reader = PdfReader(file_path)
        text = ""
        for page in reader.pages:
            text += page.extract_text() or ""
        return text.strip()
    except Exception:
        # Fallback to PyMuPDF
        try:
            doc = pymupdf.open(file_path)
            text = ""
            for page in doc:
                text += page.get_text()
            doc.close()
            return text.strip()
        except Exception:
            raise ValueError("Could not extract text from PDF")


def summarize_pdf(file_path):
    """Extract text from PDF and return it for summarization."""
    text = extract_text_from_pdf(file_path)
    return text


def translate_text(text, target_language="english"):
    """Placeholder for translation - returns original text with note."""
    return f"[Translation to {target_language} would occur here]\n\n{text[:2000]}"


def answer_question(text, question):
    """Placeholder for Q&A - returns relevant text snippet."""
    # Simple keyword matching for demonstration
    # In production, this would use an LLM API
    keywords = question.lower().split()
    relevant_sentences = []
    sentences = text.split('.')
    for sentence in sentences:
        if any(kw in sentence.lower() for kw in keywords):
            relevant_sentences.append(sentence.strip())
    if relevant_sentences:
        return ". ".join(relevant_sentences) + "."
    return "No relevant information found in the document."