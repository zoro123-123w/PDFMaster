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

# Default model – replaced by llama-3.3-70b-versatile after Groq deprecated it
# (shut-down date: 2026-08-16).
DEFAULT_MODEL = 'openai/gpt-oss-120b'
DEFAULT_PROVIDER = 'groq'
DEFAULT_BASE_URL = 'https://api.groq.com/openai/v1'


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


def _classify_openai_error(exc, model):
    """Map an openai exception to a user-facing AIServiceError.

    The API key is NEVER included in log messages or error strings.
    Only the exception type name, HTTP status code, and model name are logged.
    """
    import openai

    exc_type_name = type(exc).__name__

    # --- Authentication / authorization ----------------------------------
    if isinstance(exc, openai.AuthenticationError):
        logger.error(
            'AI authentication failed (status=%s). '
            'The API key is invalid or has been revoked. '
            'Model attempted: %s',
            getattr(exc, 'status_code', 'N/A'), model)
        raise AIServiceError(
            'The AI API key is invalid or has been revoked. '
            'Please verify AI_API_KEY in your environment.')

    # --- Model not found (deprecated / wrong model) ----------------------
    if isinstance(exc, openai.NotFoundError):
        logger.error(
            'AI model not found (status=%s). '
            'The configured model "%s" is not available on this provider. '
            'Check AI_DEFAULT_MODEL in your environment.',
            getattr(exc, 'status_code', 'N/A'), model)
        raise AIServiceError(
            f'The configured AI model "{model}" is not available. '
            f'Please set AI_DEFAULT_MODEL to a supported model for your provider.')

    # --- Rate limiting ---------------------------------------------------
    if isinstance(exc, openai.RateLimitError):
        logger.error(
            'AI rate limit exceeded (status=%s). Model: %s',
            getattr(exc, 'status_code', 'N/A'), model)
        raise AIServiceError(
            'The AI service is temporarily rate-limited. '
            'Please try again in a minute.')

    # --- Request too large / context window -------------------------------
    if isinstance(exc, openai.BadRequestError):
        # Extract the error body for the log, but never include the API key.
        body = ''
        if hasattr(exc, 'response'):
            try:
                body = exc.response.json()
            except Exception:
                body = str(getattr(exc.response, 'text', exc))
        logger.error(
            'AI bad request (status=%s) for model %s. '
            'Response body (API key redacted): %s',
            getattr(exc, 'status_code', 'N/A'), model, body)
        raise AIServiceError(
            'The AI request was rejected (possibly due to prompt length '
            'or unsupported parameters). Check server logs for details.')

    # --- Timeout ---------------------------------------------------------
    # Must come before APIConnectionError because APITimeoutError is a
    # subclass of APIConnectionError.
    if isinstance(exc, openai.APITimeoutError):
        logger.error(
            'AI request timed out. Model: %s — exception: %s',
            model, exc_type_name)
        raise AIServiceError(
            'The AI service timed out. Please try again.')

    # --- Connection / network --------------------------------------------
    if isinstance(exc, openai.APIConnectionError):
        logger.error('AI connection failure for model %s: %s', model, exc_type_name)
        raise AIServiceError(
            'Could not connect to the AI service. Please try again later.')

    # --- Generic API error -----------------------------------------------
    if isinstance(exc, openai.APIError):
        body = ''
        if hasattr(exc, 'response'):
            try:
                body = exc.response.json()
            except Exception:
                body = str(getattr(exc.response, 'text', exc))
        logger.error(
            'AI API error: %s (status=%s). Model: %s. '
            'Response body (API key redacted): %s',
            exc_type_name,
            getattr(exc, 'status_code', 'N/A'),
            model, body)
        raise AIServiceError(
            'The AI service returned an error. Check the server logs '
            'for details.')

    # --- Fallback for anything unexpected --------------------------------
    logger.error(
        'Unexpected AI provider error: %s — %s',
        exc_type_name, str(exc)[:500])
    raise AIServiceError(
        'An unexpected error occurred with the AI service. '
        'Check the server logs for details.')


class OpenAIProvider(AIProvider):
    """Provider backed by the official ``openai`` library (>=1.0).

    Works with any OpenAI-compatible endpoint (OpenAI, Groq, OpenRouter,
    local Ollama). The model, base_url, and API key come entirely from
    Django settings, which are populated from environment variables.
    """

    def __init__(self):
        self.api_key = getattr(settings, 'AI_API_KEY', '') or ''
        self.base_url = getattr(settings, 'AI_BASE_URL', '') or None
        self.model = getattr(settings, 'AI_DEFAULT_MODEL', DEFAULT_MODEL)
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
            logger.error('AI provider called with empty user_prompt.')
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
                logger.error(
                    'AI returned empty choices list (model=%s). Response: %s',
                    self.model, resp)
                raise AIServiceError(
                    'The AI returned an empty response. '
                    'The API call may have been interrupted. Please try again.')
            message = resp.choices[0].message
            if not message or not message.content:
                logger.error(
                    'AI returned a message with no content (model=%s). '
                    'finish_reason=%s',
                    self.model,
                    getattr(resp.choices[0], 'finish_reason', 'unknown'))
                raise AIServiceError(
                    'The AI returned an empty response. '
                    'The API call may have been interrupted. Please try again.')
            return message.content.strip()
        except AIServiceError:
            raise
        except Exception as exc:
            try:
                _classify_openai_error(exc, self.model)
            except AIServiceError:
                raise
            except Exception as classify_exc:
                logger.exception(
                    'Error classifier failed (model=%s): %s — original exc: %s',
                    self.model, type(classify_exc).__name__, type(exc).__name__)
                raise AIServiceError(
                    'The AI service returned an unexpected error. '
                    'Check the server logs for details.') from exc


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

    provider_name = provider_name or DEFAULT_PROVIDER
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
    if not provider:
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
