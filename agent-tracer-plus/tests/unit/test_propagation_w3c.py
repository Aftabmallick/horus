"""Tests for W3C Trace Context propagation."""

import pytest

from agent_tracer_plus.propagation.w3c import (
    TraceContextData,
    W3CTraceContextPropagator,
    extract_context,
    inject_context,
)


class TestW3CExtract:
    def test_valid_traceparent(self):
        headers = {"traceparent": "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"}
        data = extract_context(headers)
        assert data is not None
        assert data.trace_id == "4bf92f3577b34da6a3ce929d0e0e4736"
        assert data.span_id == "00f067aa0ba902b7"
        assert data.trace_flags == 1

    def test_unsampled_trace(self):
        headers = {"traceparent": "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-00"}
        data = extract_context(headers)
        assert data is not None
        assert data.trace_flags == 0

    def test_empty_headers(self):
        data = extract_context({})
        assert data is None

    def test_missing_traceparent(self):
        data = extract_context({"other-header": "value"})
        assert data is None

    def test_invalid_format_too_short(self):
        data = extract_context({"traceparent": "00-abcdef"})
        assert data is None

    def test_invalid_format_bad_chars(self):
        data = extract_context({"traceparent": "00-ZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZ-0000000000000000-01"})
        assert data is None

    def test_whitespace_trimmed(self):
        headers = {"traceparent": "  00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01  "}
        data = extract_context(headers)
        assert data is not None
        assert data.trace_id == "4bf92f3577b34da6a3ce929d0e0e4736"


class TestW3CInject:
    def test_no_context_no_injection(self):
        """Without active trace/span, inject should not add traceparent."""
        headers = {}
        result = inject_context(headers)
        assert "traceparent" not in result

    def test_preserves_existing_headers(self):
        headers = {"Authorization": "Bearer token"}
        result = inject_context(headers)
        assert result["Authorization"] == "Bearer token"


class TestTraceContextData:
    def test_attributes(self):
        data = TraceContextData(trace_id="abc123", span_id="def456", trace_flags=1)
        assert data.trace_id == "abc123"
        assert data.span_id == "def456"
        assert data.trace_flags == 1

    def test_default_flags(self):
        data = TraceContextData(trace_id="abc", span_id="def")
        assert data.trace_flags == 1
