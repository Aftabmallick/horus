"""Tests for OpenAI auto-instrumentation — idempotency, data extraction, patching flag."""

import pytest
from unittest.mock import MagicMock, patch

from agent_tracer_plus.auto.openai_instr import _PATCHED


class TestOpenAIInstrIdempotency:
    def test_patched_flag_exists(self):
        """The module should have a _PATCHED guard."""
        from agent_tracer_plus.auto import openai_instr
        assert hasattr(openai_instr, "_PATCHED")

    def test_double_patch_is_noop(self):
        """Calling patch_openai() twice should not raise or double-wrap."""
        from agent_tracer_plus.auto.openai_instr import patch_openai

        # First call may or may not succeed depending on openai being installed
        # But calling twice should never crash
        try:
            patch_openai()
            patch_openai()  # Second call should be a no-op
        except ImportError:
            pytest.skip("openai not installed")


class TestExtractResponseData:
    def test_extract_from_mock_response(self):
        """_extract_response_data should pull token usage and content from a response object."""
        from agent_tracer_plus.auto.openai_instr import _extract_response_data

        # Create a mock response mimicking openai.ChatCompletion
        mock_usage = MagicMock()
        mock_usage.prompt_tokens = 100
        mock_usage.completion_tokens = 50
        mock_usage.total_tokens = 150

        mock_choice = MagicMock()
        mock_choice.message.content = "Hello, world!"
        mock_choice.finish_reason = "stop"

        mock_response = MagicMock()
        mock_response.usage = mock_usage
        mock_response.choices = [mock_choice]
        mock_response.model = "gpt-4o-mini"
        mock_response.id = "chatcmpl-123"

        mock_span = MagicMock()
        _extract_response_data(mock_span, mock_response, "gpt-4o-mini")

        assert mock_span.set_output.called
        assert mock_span.token_usage.input_tokens == 100
        assert mock_span.token_usage.output_tokens == 50
        assert mock_span.token_usage.total_tokens == 150

    def test_extract_with_none_usage(self):
        """Handle responses with missing usage data gracefully."""
        from agent_tracer_plus.auto.openai_instr import _extract_response_data

        mock_choice = MagicMock()
        mock_choice.message.content = "result"
        mock_choice.finish_reason = "stop"

        mock_response = MagicMock()
        mock_response.usage = None
        mock_response.choices = [mock_choice]
        mock_response.model = "gpt-4o"
        mock_response.id = "chatcmpl-456"

        mock_span = MagicMock()
        _extract_response_data(mock_span, mock_response, "gpt-4o")

        assert mock_span.set_output.called
        assert isinstance(mock_span.token_usage, MagicMock)

    def test_extract_empty_choices(self):
        """Handle responses with no choices."""
        from agent_tracer_plus.auto.openai_instr import _extract_response_data

        mock_response = MagicMock()
        mock_response.usage = None
        mock_response.choices = []
        mock_response.model = "gpt-4o"
        mock_response.id = "chatcmpl-789"

        mock_span = MagicMock()
        _extract_response_data(mock_span, mock_response, "gpt-4o")

        assert not mock_span.set_output.called
