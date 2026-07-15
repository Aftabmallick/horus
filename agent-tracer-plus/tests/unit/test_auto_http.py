"""Tests for HTTP auto-instrumentation — header injection, patching flags."""

import pytest

from agent_tracer_plus.core.context import SpanContext, TraceContext, get_current_span, get_current_trace
from agent_tracer_plus.auto.http_instr import _inject_trace_headers


class TestInjectTraceHeaders:
    def test_injects_traceparent_when_context_active(self):
        with TraceContext(agent_name="HTTPTest") as trace:
            with SpanContext(name="span") as span:
                headers = {}
                result = _inject_trace_headers(headers)
                assert "traceparent" in result
                assert trace.trace_id in result["traceparent"]
                assert span.span_id in result["traceparent"]
                assert result["traceparent"].startswith("00-")

    def test_no_injection_without_context(self):
        headers = {}
        result = _inject_trace_headers(headers)
        assert "traceparent" not in result

    def test_preserves_existing_headers(self):
        with TraceContext(agent_name="T"):
            with SpanContext(name="s"):
                headers = {"Authorization": "Bearer xyz", "Content-Type": "application/json"}
                result = _inject_trace_headers(headers)
                assert result["Authorization"] == "Bearer xyz"
                assert result["Content-Type"] == "application/json"
                assert "traceparent" in result


class TestPatchFlags:
    def test_httpx_flag_exists(self):
        from agent_tracer_plus.auto.http_instr import _HTTPX_PATCHED
        # Flag should be either True or False, not missing
        assert isinstance(_HTTPX_PATCHED, bool)

    def test_requests_flag_exists(self):
        from agent_tracer_plus.auto.http_instr import _REQUESTS_PATCHED
        assert isinstance(_REQUESTS_PATCHED, bool)

    def test_double_patch_httpx_is_safe(self):
        from agent_tracer_plus.auto.http_instr import patch_httpx
        try:
            patch_httpx()
            patch_httpx()
        except ImportError:
            pytest.skip("httpx not installed")

    def test_double_patch_requests_is_safe(self):
        from agent_tracer_plus.auto.http_instr import patch_requests
        try:
            patch_requests()
            patch_requests()
        except ImportError:
            pytest.skip("requests not installed")
