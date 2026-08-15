"""AI provider abstraction.

Provides a clean, pluggable interface so the project can talk to any
OpenAI-compatible chat API (OpenAI, OpenRouter, local Ollama/OpenAI endpoint, …)
without hard-coding keys or model names.

All configuration is read from Django settings which themselves come from
environment variables – the API key is never logged or exposed to templates.
"""
import logging

from django.conf import settings

logger = logging.getLogger(__name__)


class AIServiceError(Exception):
    """Raised when the AI provider cannot fulfil a request."""


class AIProvider:
    """Base interface for an AI chat provider."""

    def chat(self, system_prompt, user_prompt, max_tokens=2000, temperature=0.7):
        """Return a text completion. Subclasses must implement this."""
        raise NotImplementedError


class OpenAIProvider(AIProvider):
    """Provider backed by the official ``openai`` library (>=1.0)."""

    def __init__(self):
        self.api_key = getattr(settings, 'AI_API_KEY', '') or ''
        self.base_url = getattr(settings, 'AI_BASE_URL', '') or None
        self.model = getattr(settings, 'AI_DEFAULT_MODEL', 'gpt-4o-mini')

    def _client(self):
        import openai
        kwargs = {}
        if self.base_url:
            kwargs['base_url'] = self.base_url
        return openai.OpenAI(api_key=self.api_key, **kwargs)

    def chat(self, system_prompt, user_prompt, max_tokens=2000, temperature=0.7):
        if not self.api_key:
            raise AIServiceError(
                'AI_API_KEY is not configured. Set it in your environment '
                'to enable AI-powered features.')
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
            return resp.choices[0].message.content or ''
        except Exception as exc:
            # Never leak the raw API error / key to the user; log internally only.
            logger.warning('OpenAI provider error: %s', type(exc).__name__)
            raise AIServiceError(
                'The AI service is temporarily unavailable. Please try again later.')


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

    # Currently only ``openai`` is supported but the abstraction allows
    # registering new providers here (e.g. Anthropic, Gemini) by adding a
    # mapping and a corresponding provider class.
    provider_name = provider_name or 'openai'
    if provider_name in ('openai', 'openrouter', 'ollama'):
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

    Raises :class:`AIServiceError` when no provider is configured or the call
    fails.
    """
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
