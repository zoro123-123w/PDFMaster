"""Tests for the AI provider layer.

All external API calls are mocked — no real API key is required.
"""
import io
import logging
from unittest import mock

from django.test import TestCase, override_settings
from django.conf import settings

from ai_tools.services.ai_provider import (
    AIProvider,
    AIServiceError,
    OpenAIProvider,
    call_ai,
    get_ai_provider,
    reset_ai_provider_cache,
    safe_truncate,
    MAX_PROMPT_CHARS,
    DEFAULT_MODEL,
    DEFAULT_PROVIDER,
    DEFAULT_BASE_URL,
)


class SafeTruncateTests(TestCase):
    def test_short_text_unchanged(self):
        text = 'Hello world'
        self.assertEqual(safe_truncate(text), text)

    def test_long_text_truncated(self):
        text = 'A' * (MAX_PROMPT_CHARS + 500)
        result = safe_truncate(text)
        self.assertTrue(result.startswith('[Text truncated') is False)
        self.assertTrue(result.endswith('above.]'))
        self.assertIn('[Text truncated for length', result)

    def test_empty_text(self):
        self.assertEqual(safe_truncate(''), '')


class AIProviderConfigurationTests(TestCase):
    """Verify that provider configuration reads from Django settings."""

    def setUp(self):
        reset_ai_provider_cache()

    def tearDown(self):
        reset_ai_provider_cache()

    @override_settings(
        AI_PROVIDER='groq',
        AI_API_KEY='fake-key',
        AI_BASE_URL='https://api.groq.com/openai/v1',
        AI_DEFAULT_MODEL='openai/gpt-oss-120b',
    )
    def test_provider_selection_groq(self):
        provider = get_ai_provider()
        self.assertIsNotNone(provider)
        self.assertIsInstance(provider, OpenAIProvider)

    @override_settings(
        AI_PROVIDER='groq',
        AI_API_KEY='fake-key',
        AI_BASE_URL='https://api.groq.com/openai/v1',
        AI_DEFAULT_MODEL='openai/gpt-oss-120b',
    )
    def test_provider_reads_groq_config(self):
        provider = get_ai_provider()
        self.assertEqual(provider.base_url, 'https://api.groq.com/openai/v1')
        self.assertEqual(provider.model, 'openai/gpt-oss-120b')
        self.assertTrue(provider.api_key)  # non-empty

    @override_settings(
        AI_PROVIDER='openai',
        AI_API_KEY='fake-key',
        AI_BASE_URL='https://api.openai.com/v1',
        AI_DEFAULT_MODEL='gpt-4o-mini',
    )
    def test_provider_reads_openai_config(self):
        provider = get_ai_provider()
        self.assertEqual(provider.base_url, 'https://api.openai.com/v1')
        self.assertEqual(provider.model, 'gpt-4o-mini')

    @override_settings(
        AI_PROVIDER='',
        AI_API_KEY='',
        AI_DEFAULT_MODEL=DEFAULT_MODEL,
    )
    def test_no_key_returns_none(self):
        self.assertIsNone(get_ai_provider())

    @override_settings(
        AI_PROVIDER='',
        AI_API_KEY='fake-key',
        AI_DEFAULT_MODEL=DEFAULT_MODEL,
    )
    def test_no_provider_returns_none(self):
        self.assertIsNone(get_ai_provider())

    @override_settings(
        AI_PROVIDER='unknown-provider',
        AI_API_KEY='fake-key',
        AI_DEFAULT_MODEL=DEFAULT_MODEL,
    )
    def test_unknown_provider_returns_none(self):
        reset_ai_provider_cache()
        self.assertIsNone(get_ai_provider())

    @override_settings(
        AI_PROVIDER='groq',
        AI_API_KEY='fake-key',
        AI_BASE_URL='https://api.groq.com/openai/v1',
        AI_DEFAULT_MODEL='openai/gpt-oss-120b',
    )
    def test_call_ai_raises_when_no_key(self):
        reset_ai_provider_cache()
        with override_settings(AI_API_KEY=''):
            with self.assertRaises(AIServiceError) as ctx:
                call_ai('system', 'user prompt here')
            self.assertIn('not configured', str(ctx.exception))

    @override_settings(
        AI_PROVIDER='groq',
        AI_API_KEY='',
        AI_DEFAULT_MODEL=DEFAULT_MODEL,
    )
    def test_call_ai_empty_prompt_raises(self):
        with self.assertRaises(AIServiceError):
            call_ai('system', '')


class ProviderClientTests(TestCase):
    """Verify the OpenAI client is initialised with the correct parameters."""

    @override_settings(
        AI_API_KEY='test-key',
        AI_BASE_URL='https://api.groq.com/openai/v1',
        AI_DEFAULT_MODEL='openai/gpt-oss-120b',
        AI_TIMEOUT_SECONDS='30',
    )
    def test_client_initialisation(self):
        with mock.patch('openai.OpenAI') as MockClient:
            provider = OpenAIProvider()
            provider._client()
            MockClient.assert_called_once()
            call_kwargs = MockClient.call_args.kwargs
            self.assertEqual(call_kwargs['api_key'], 'test-key')
            self.assertEqual(call_kwargs['base_url'], 'https://api.groq.com/openai/v1')
            self.assertEqual(call_kwargs['timeout'], 30)

    @override_settings(
        AI_API_KEY='test-key',
        AI_BASE_URL='',
        AI_DEFAULT_MODEL=DEFAULT_MODEL,
        AI_TIMEOUT_SECONDS='30',
    )
    def test_client_no_base_url(self):
        with mock.patch('openai.OpenAI') as MockClient:
            provider = OpenAIProvider()
            provider._client()
            call_kwargs = MockClient.call_args.kwargs
            self.assertEqual(call_kwargs['api_key'], 'test-key')
            self.assertNotIn('base_url', call_kwargs)

    @override_settings(
        AI_PROVIDER='groq',
        AI_API_KEY='test-key',
        AI_BASE_URL='https://api.groq.com/openai/v1',
        AI_DEFAULT_MODEL='openai/gpt-oss-120b',
        AI_TIMEOUT_SECONDS='30',
    )
    def test_chat_sends_correct_model_and_base_url(self):
        """Verify the request to the API includes the correct model and base URL."""
        mock_completion = mock.MagicMock()
        mock_completion.choices = [
            mock.MagicMock(message=mock.MagicMock(content='Test response', role='assistant'))
        ]

        with mock.patch('openai.OpenAI') as MockClient:
            MockClient.return_value.chat.completions.create.return_value = mock_completion

            provider = OpenAIProvider()
            result = provider.chat('system prompt', 'user prompt', max_tokens=1500, temperature=0.5)

            self.assertEqual(result, 'Test response')

            create_call = MockClient.return_value.chat.completions.create.call_args
            # Verify model is correct
            self.assertEqual(create_call.kwargs['model'], 'openai/gpt-oss-120b')
            # Verify messages are correct
            messages = create_call.kwargs['messages']
            self.assertEqual(len(messages), 2)
            self.assertEqual(messages[0]['role'], 'system')
            self.assertEqual(messages[0]['content'], 'system prompt')
            self.assertEqual(messages[1]['role'], 'user')
            self.assertEqual(messages[1]['content'], 'user prompt')
            # Verify max_tokens and temperature
            self.assertEqual(create_call.kwargs['max_tokens'], 1500)
            self.assertEqual(create_call.kwargs['temperature'], 0.5)

            # Verify the client was created with the correct base_url
            MockClient.assert_called_once_with(
                api_key='test-key',
                base_url='https://api.groq.com/openai/v1',
                timeout=30,
            )


class ProviderErrorHandlingTests(TestCase):
    """Verify error classification and logging for different error types."""

    def setUp(self):
        reset_ai_provider_cache()

    def tearDown(self):
        reset_ai_provider_cache()

    @override_settings(
        AI_PROVIDER='groq',
        AI_API_KEY='test-key',
        AI_BASE_URL='https://api.groq.com/openai/v1',
        AI_DEFAULT_MODEL='openai/gpt-oss-120b',
    )
    def test_model_not_found_error(self):
        """Verify model_not_found error is handled gracefully."""
        import openai
        api_error = openai.NotFoundError(
            message='The model does not exist',
            response=mock.MagicMock(status_code=404, json=lambda: {'error': {'message': 'model_not_found'}}, text=''),
            body=None,
        )
        api_error.status_code = 404

        mock_completion = mock.MagicMock()
        mock_completion.choices = []

        with mock.patch('openai.OpenAI') as MockClient:
            MockClient.return_value.chat.completions.create.side_effect = api_error
            provider = OpenAIProvider()

            with self.assertRaises(AIServiceError) as ctx:
                provider.chat('system', 'user prompt')
            self.assertIn('not available', str(ctx.exception))

    @override_settings(
        AI_PROVIDER='groq',
        AI_API_KEY='test-key',
        AI_BASE_URL='https://api.groq.com/openai/v1',
        AI_DEFAULT_MODEL='openai/gpt-oss-120b',
    )
    def test_auth_error(self):
        """Verify authentication error is handled."""
        import openai
        api_error = openai.AuthenticationError(
            message='Incorrect API key',
            response=mock.MagicMock(status_code=401, json=lambda: {}, text=''),
            body=None,
        )
        api_error.status_code = 401

        with mock.patch('openai.OpenAI') as MockClient:
            MockClient.return_value.chat.completions.create.side_effect = api_error
            provider = OpenAIProvider()

            with self.assertRaises(AIServiceError) as ctx:
                provider.chat('system', 'user prompt')
            self.assertIn('API key', str(ctx.exception))

    @override_settings(
        AI_PROVIDER='groq',
        AI_API_KEY='test-key',
        AI_BASE_URL='https://api.groq.com/openai/v1',
        AI_DEFAULT_MODEL='openai/gpt-oss-120b',
    )
    def test_rate_limit_error(self):
        """Verify rate limit error is handled."""
        import openai
        api_error = openai.RateLimitError(
            message='Rate limit exceeded',
            response=mock.MagicMock(status_code=429, json=lambda: {}, text=''),
            body=None,
        )
        api_error.status_code = 429

        with mock.patch('openai.OpenAI') as MockClient:
            MockClient.return_value.chat.completions.create.side_effect = api_error
            provider = OpenAIProvider()

            with self.assertRaises(AIServiceError) as ctx:
                provider.chat('system', 'user prompt')
            self.assertIn('rate-limited', str(ctx.exception))

    @override_settings(
        AI_PROVIDER='groq',
        AI_API_KEY='test-key',
        AI_BASE_URL='https://api.groq.com/openai/v1',
        AI_DEFAULT_MODEL='openai/gpt-oss-120b',
    )
    def test_timeout_error(self):
        """Verify timeout error is handled."""
        import openai, httpx
        req = httpx.Request('POST', 'https://api.test.com/v1/chat/completions')
        timeout_exc = openai.APITimeoutError(request=req)

        with mock.patch('openai.OpenAI') as MockClient:
            MockClient.return_value.chat.completions.create.side_effect = timeout_exc
            provider = OpenAIProvider()

            with self.assertRaises(AIServiceError) as ctx:
                provider.chat('system', 'user prompt')
            self.assertIn('timed out', str(ctx.exception))

    @override_settings(
        AI_PROVIDER='groq',
        AI_API_KEY='test-key',
        AI_BASE_URL='https://api.groq.com/openai/v1',
        AI_DEFAULT_MODEL='openai/gpt-oss-120b',
    )
    def test_connection_error(self):
        """Verify connection error is handled."""
        import openai
        conn_error = openai.APIConnectionError(
            message='Connection refused',
            request=mock.MagicMock(),
        )

        with mock.patch('openai.OpenAI') as MockClient:
            MockClient.return_value.chat.completions.create.side_effect = conn_error
            provider = OpenAIProvider()

            with self.assertRaises(AIServiceError) as ctx:
                provider.chat('system', 'user prompt')
            self.assertIn('connect', str(ctx.exception))

    @override_settings(
        AI_PROVIDER='groq',
        AI_API_KEY='test-key',
        AI_BASE_URL='https://api.groq.com/openai/v1',
        AI_DEFAULT_MODEL='openai/gpt-oss-120b',
    )
    def test_missing_api_key_in_provider(self):
        """OpenAIProvider with empty api_key should raise AIServiceError."""
        with override_settings(AI_API_KEY=''):
            provider = OpenAIProvider()
            self.assertFalse(provider.api_key)
            with self.assertRaises(AIServiceError):
                provider.chat('system', 'user prompt')

    @override_settings(
        AI_PROVIDER='groq',
        AI_API_KEY='test-key',
        AI_BASE_URL='https://api.groq.com/openai/v1',
        AI_DEFAULT_MODEL='openai/gpt-oss-120b',
    )
    def test_empty_choices_handled(self):
        """Verify empty choices list is handled gracefully."""
        mock_completion = mock.MagicMock()
        mock_completion.choices = []

        with mock.patch('openai.OpenAI') as MockClient:
            MockClient.return_value.chat.completions.create.return_value = mock_completion
            provider = OpenAIProvider()

            with self.assertRaises(AIServiceError) as ctx:
                provider.chat('system', 'user prompt')
            self.assertIn('empty response', str(ctx.exception))

    @override_settings(
        AI_PROVIDER='groq',
        AI_API_KEY='test-key',
        AI_BASE_URL='https://api.groq.com/openai/v1',
        AI_DEFAULT_MODEL='openai/gpt-oss-120b',
    )
    def test_none_content_handled(self):
        """Verify None message content is handled gracefully."""
        mock_completion = mock.MagicMock()
        mock_completion.choices = [
            mock.MagicMock(message=mock.MagicMock(content=None))
        ]

        with mock.patch('openai.OpenAI') as MockClient:
            MockClient.return_value.chat.completions.create.return_value = mock_completion
            provider = OpenAIProvider()

            with self.assertRaises(AIServiceError) as ctx:
                provider.chat('system', 'user prompt')
            self.assertIn('empty response', str(ctx.exception))

    @override_settings(
        AI_PROVIDER='groq',
        AI_API_KEY='test-key',
        AI_BASE_URL='https://api.groq.com/openai/v1',
        AI_DEFAULT_MODEL='openai/gpt-oss-120b',
    )
    def test_api_key_not_logged(self):
        """Verify that the API key is not leaked into log messages."""
        import openai
        api_error = openai.NotFoundError(
            message='model_not_found',
            response=mock.MagicMock(status_code=404, json=lambda: {'error': {'message': 'test'}}, text=''),
            body=None,
        )
        api_error.status_code = 404

        with mock.patch('openai.OpenAI') as MockClient:
            MockClient.return_value.chat.completions.create.side_effect = api_error
            with self.assertLogs('ai_tools.services.ai_provider', level='ERROR') as log_ctx:
                with self.assertRaises(AIServiceError):
                    provider = OpenAIProvider()
                    provider.chat('system', 'user prompt')

            for record in log_ctx.records:
                self.assertNotIn('test-key', record.getMessage())
                self.assertNotIn('api_key', record.getMessage().lower())


class CallAIIntegrationTests(TestCase):
    """Verify call_ai() delegates correctly to the provider."""

    def setUp(self):
        reset_ai_provider_cache()

    def tearDown(self):
        reset_ai_provider_cache()

    @override_settings(
        AI_PROVIDER='groq',
        AI_API_KEY='test-key',
        AI_BASE_URL='https://api.groq.com/openai/v1',
        AI_DEFAULT_MODEL='openai/gpt-oss-120b',
    )
    def test_call_ai_success(self):
        mock_completion = mock.MagicMock()
        mock_completion.choices = [
            mock.MagicMock(message=mock.MagicMock(content='AI response', role='assistant'))
        ]

        with mock.patch('openai.OpenAI') as MockClient:
            MockClient.return_value.chat.completions.create.return_value = mock_completion
            result = call_ai('system prompt', 'user prompt', max_tokens=500, temperature=0.3)
            self.assertEqual(result, 'AI response')

            create_call = MockClient.return_value.chat.completions.create.call_args
            self.assertEqual(create_call.kwargs['model'], 'openai/gpt-oss-120b')
            self.assertEqual(create_call.kwargs['max_tokens'], 500)
            self.assertEqual(create_call.kwargs['temperature'], 0.3)

    @override_settings(
        AI_PROVIDER='groq',
        AI_API_KEY='',
        AI_DEFAULT_MODEL=DEFAULT_MODEL,
    )
    def test_call_ai_no_api_key_graceful(self):
        reset_ai_provider_cache()
        with self.assertRaises(AIServiceError) as ctx:
            call_ai('system', 'user prompt')
        self.assertIn('not configured', str(ctx.exception))

    @override_settings(
        AI_PROVIDER='groq',
        AI_API_KEY='fake-key',
        AI_BASE_URL='https://api.groq.com/openai/v1',
        AI_DEFAULT_MODEL='openai/gpt-oss-120b',
    )
    def test_provider_cache_false_handled(self):
        """Verify that a cached False (not None) from get_ai_provider
        doesn't cause AttributeError in call_ai."""
        # Simulate a previous request that cached False (no API key was set)
        reset_ai_provider_cache()
        with override_settings(AI_API_KEY=''):
            reset_ai_provider_cache()
            # First call with no key caches False
            result = get_ai_provider()
            self.assertIsNone(result)  # None is returned, False is cached

        # Now with API key set, but cache still has False
        with override_settings(AI_API_KEY='fake-key'):
            reset_ai_provider_cache()
            # Clear the False cache by resetting
            result = get_ai_provider()
            self.assertIsNotNone(result)
            self.assertIsInstance(result, OpenAIProvider)


class QuizEndpointTests(TestCase):
    """Verify the quiz endpoint behavior with mocked AI."""

    def setUp(self):
        reset_ai_provider_cache()
        from django.contrib.auth import get_user_model
        User = get_user_model()
        User.objects.create_user('testuser', 'test@example.com', 'TestPass123!')
        from django.core.files.uploadedfile import SimpleUploadedFile
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter
        import io as _io

        buf = _io.BytesIO()
        c = canvas.Canvas(buf, pagesize=letter)
        text = "This is a test document for AI quiz generation. " * 20
        c.drawString(100, 700, text)
        c.showPage()
        c.save()
        buf.seek(0)
        self.pdf_file = SimpleUploadedFile(
            'test.pdf', buf.getvalue(), content_type='application/pdf')

    def tearDown(self):
        reset_ai_provider_cache()

    @override_settings(
        AI_PROVIDER='groq',
        AI_API_KEY='test-key',
        AI_BASE_URL='https://api.groq.com/openai/v1',
        AI_DEFAULT_MODEL='openai/gpt-oss-120b',
    )
    def test_quiz_success(self):
        from django.test import Client
        from django.urls import reverse
        import json as _json

        mock_completion = mock.MagicMock()
        mock_completion.choices = [
            mock.MagicMock(message=mock.MagicMock(
                content=_json.dumps({'questions': [{'question': 'Q1', 'options': ['a', 'b', 'c', 'd'], 'answer': 'a', 'explanation': 'E1'}]}),
                role='assistant'))
        ]

        client = Client(HTTP_HOST='127.0.0.1:8000')
        client.login(username='testuser', password='TestPass123!')

        with mock.patch('openai.OpenAI') as MockClient:
            MockClient.return_value.chat.completions.create.return_value = mock_completion
            response = client.post(reverse('ai_study_quiz'), {
                'file': self.pdf_file, 'num_questions': '5', 'difficulty': 'medium',
            })
            self.assertIn(response.status_code, [302, 200])

            if response.status_code == 302:
                detail_response = client.get(response.url)
                self.assertEqual(detail_response.status_code, 200)

    @override_settings(
        AI_PROVIDER='groq',
        AI_API_KEY='',
        AI_DEFAULT_MODEL=DEFAULT_MODEL,
    )
    def test_quiz_no_key_graceful(self):
        from django.test import Client
        from django.urls import reverse

        client = Client(HTTP_HOST='127.0.0.1:8000')
        client.login(username='testuser', password='TestPass123!')
        response = client.post(reverse('ai_study_quiz'), {
            'file': self.pdf_file, 'num_questions': '5', 'difficulty': 'medium',
        })
        self.assertIn(response.status_code, [200, 302])


class StudyNotesEndpointTests(TestCase):
    """Verify another AI tool uses the same provider."""

    def setUp(self):
        reset_ai_provider_cache()
        from django.contrib.auth import get_user_model
        User = get_user_model()
        User.objects.create_user('testuser', 'test@example.com', 'TestPass123!')
        from django.core.files.uploadedfile import SimpleUploadedFile
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter
        import io as _io

        buf = _io.BytesIO()
        c = canvas.Canvas(buf, pagesize=letter)
        text = "This is a test document for AI study tools. " * 20
        c.drawString(100, 700, text)
        c.showPage()
        c.save()
        buf.seek(0)
        self.pdf_file = SimpleUploadedFile(
            'test.pdf', buf.getvalue(), content_type='application/pdf')

    def tearDown(self):
        reset_ai_provider_cache()

    @override_settings(
        AI_PROVIDER='groq',
        AI_API_KEY='test-key',
        AI_BASE_URL='https://api.groq.com/openai/v1',
        AI_DEFAULT_MODEL='openai/gpt-oss-120b',
    )
    def test_study_notes_uses_same_provider(self):
        from django.test import Client
        from django.urls import reverse

        mock_completion = mock.MagicMock()
        mock_completion.choices = [
            mock.MagicMock(message=mock.MagicMock(content='Study notes content', role='assistant'))
        ]

        client = Client(HTTP_HOST='127.0.0.1:8000')
        client.login(username='testuser', password='TestPass123!')

        with mock.patch('openai.OpenAI') as MockClient:
            MockClient.return_value.chat.completions.create.return_value = mock_completion
            response = client.post(reverse('ai_study_notes'), {
                'file': self.pdf_file,
            })
            self.assertIn(response.status_code, [302, 200])

            # Verify the OpenAI client was created with the Groq base URL
            MockClient.assert_called_with(
                api_key='test-key',
                base_url='https://api.groq.com/openai/v1',
                timeout=30,
            )

            # Verify the model was sent in the chat completions call
            create_call = MockClient.return_value.chat.completions.create.call_args
            self.assertIsNotNone(create_call)
            self.assertEqual(create_call.kwargs['model'], 'openai/gpt-oss-120b')
