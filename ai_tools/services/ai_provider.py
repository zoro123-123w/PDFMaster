"""AI provider abstraction.

Provides a clean, pluggable interface so the project can talk to any
OpenAI-compatible chat API (OpenAI, OpenRouter, Groq, local Ollama/OpenAI endpoint)
without hard-coding keys or model names.

All configuration is read from Django settings which themselves come from
environment variables – the API key is never logged or exposed to templates.
"""
import logging

from django.conf import settings

logger = logging.getLogger(__name__)

# Groq (and most OpenAI-compatible providers) reject requests whose total
# prompt exceeds the model's context window with a 400 Bad Request.
# We cap the user-supplied text at 20 000 characters (~5 000 tokens) which
# gives ample head-room for the system prompt and the generated output tokens.
MAX_PROMPT_CHARS = 20_000


class AIServiceError(Exception):
    """Raised when the AI provider cannot fulfil a request."""


class ExtractionError(ValueError):
    """Raised when text cannot be extracted from a document."""


class AIProvider:
    """Base interface for an AI chat provider."""

    def chat(self, system_prompt, user_prompt, max_tokens=2000, temperature=0.7):
        """Return a text completion. Subclasses must implement this."""
        raise NotImplementedError


def safe_truncate(text, max_chars=MAX_PROMPT_CHARS):
    """Truncate *text* to *max_chars* and append a visible notification.

    The truncation note is injected **into the user prompt** so the LLM knows
    the original text was longer – this prevents the model from making
    up facts to fill the missing portion.
    """
    if not text:
        return text
    if len(text) <= max_chars:
        return text
    truncated = text[:max_chars]
    truncated += (
        f'\n\n[Text truncated for length: the original document '
        f'contained {len(text)} characters. Only the first {max_chars} '
        f'characters were sent to the model. Please rely only on the '
        f'information contained in the text above.]'
    )
    logger.warning('Truncated prompt from %d chars to %d chars', len(text), max_chars)
    return truncated


class OpenAIProvider(AIProvider):
    """Provider backed by the official ``openai`` library (>=1.0)."""

    def __init__(self):
        self.api_key = getattr(settings, 'AI_API_KEY', '') or ''
        self.base_url = getattr(settings, 'AI_BASE_URL', '') or None
        self.model = getattr(settings, 'AI_DEFAULT_MODEL', 'gpt-4o-mini')
        self.timeout = float(getattr(settings, 'AI_TIMEOUT_SECONDS', '30') or '30')

    def _client(self):
        import openai
        kwargs = {'timeout': self.timeout}
        if self.base_url:
            kwargs['base_url'] = self.base_url
        return openai.OpenAI(api_key=self.api_key, **kwargs)

    def chat(self, system_prompt, user_prompt, max_tokens=2000, temperature=0.7):
        if not self.api_key:
            raise AIServiceError(
                'AI_API_KEY is not configured. Set it in your environment '
                'to enable AI-powered features.')

        if not user_prompt or not user_prompt.strip():
            logger.error('OpenAI provider called with empty user_prompt.')
            raise AIServiceError(
                'No text content to send to the AI. The PDF may have no '
                'extractable text.')

        try:
            client = self._client()
            messages = [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt},
            ]
            resp = client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            # Safe response parsing – guard against empty choices or None content.
            if not resp.choices:
                logger.error('OpenAI returned empty choices list. Full response: %s', resp)
                raise AIServiceError(
                    'The AI returned an empty response. The API call may have '
                    'been interrupted. Please try again.')
            message = resp.choices[0].message
            if not message or not message.content:
                logger.error(
                    'OpenAI returned a message with no content. '
                    'finish_reason=%s — full message: %s',
                    getattr(resp.choices[0], 'finish_reason', 'unknown'),
                    repr(message))
                raise AIServiceError(
                    'The AI returned an empty response. The API call may '
                    'have been interrupted. Please try again.')
            return message.content.strip()
        except AIServiceError:
            raise
        except Exception as exc:
            # Log the full API response for debugging, especially for 400 errors.
            # The raw error body (e.g. from openai.BadRequestError.response.json())
            # contains the exact reason the LLM provider rejected the request.
            if hasattr(exc, 'response'):
                try:
                    error_body = exc.response.json()
                except Exception:
                    error_body = str(exc.response.text) if hasattr(exc.response, 'text') else str(exc)
                logger.error('OpenAI API error: %s — response body: %s',
                             type(exc).__name__, error_body)
            else:
                logger.error('OpenAI provider error: %s — %s',
                             type(exc).__name__, str(exc))
            raise AIServiceError(
                'The AI service returned an error. Check the server logs '
                'for the exact API response. Common causes: the prompt was '
                'too long, the model does not support the requested '
                'parameters, or the API key is invalid.')


_PROVIDER_CACHE = None


def get_ai_provider():
    """Return the configured :class:`AIProvider` or ``None`` if unconfigured."""
    global _PROVIDER_CACHE
    if _PROVIDER_CACHE is not None:
        return _PROVIDER_CACHE

    provider_name = (getattr(settings, 'AI_PROVIDER', '') or '').lower().strip()
    api_key = getattr(settings, 'AI_API_KEY', '') or ''

    if not provider_name or not api_key:
        _PROVIDER_CACHE = False  # mark as checked
        return None

    provider_name = provider_name or 'openai'
    if provider_name in ('openai', 'openrouter', 'ollama', 'groq'):
        provider = OpenAIProvider()
        _PROVIDER_CACHE = provider
        return provider

    logger.warning('Unknown AI provider: %s', provider_name)
    _PROVIDER_CACHE = False
    return None


def reset_ai_provider_cache():
    """Clear the cached provider – used in tests and after env changes."""
    global _PROVIDER_CACHE
    _PROVIDER_CACHE = None


def call_ai(system_prompt, user_prompt, max_tokens=2000, temperature=0.7):
    """Convenience wrapper: get the provider and call chat().

    Raises :class:`AIServiceError` when no provider is configured, the user
    prompt is empty, or the call fails.
    """
    if not user_prompt or not user_prompt.strip():
        logger.error('call_ai invoked with empty user_prompt.')
        raise AIServiceError(
            'No text content available to send to the AI. '
            'Ensure the PDF contains extractable text.')

    provider = get_ai_provider()
    if provider is None:
        raise AIServiceError(
            'AI service is not configured. Please set AI_API_KEY in your '
            'environment variables to use AI-powered features.')
    if provider is False:
        raise AIServiceError(
            'AI service is not configured. Please set AI_API_KEY in your '
            'environment variables to use AI-powered features.')
    return provider.chat(system_prompt, user_prompt,
                         max_tokens=max_tokens, temperature=temperature)


def truncate_text(text, max_chars=8000):
    """Truncate long text to fit within a reasonable context window."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + '\n\n[... text truncated ...]'
