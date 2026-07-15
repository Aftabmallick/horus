"""Tests for B3 (Zipkin) trace context propagation — single and multi-header."""

import pytest

from agent_tracer_plus.propagation.b3 import (
    B3Propagator,
    B3TraceContextData,
    extract_b3,
    inject_b3,
)


class TestB3Extract:
    def test_multi_header(self):
        headers = {
            "X-B3-TraceId": "463ac35c9f6413ad48485a3953bb6124",
            "X-B3-SpanId": "0020000000000001",
            "X-B3-Sampled": "1",
        }
        data = extract_b3(headers)
        assert data is not None
        assert data.trace_id == "463ac35c9f6413ad48485a3953bb6124"
        assert data.span_id == "0020000000000001"
        assert data.sampled is True
        assert data.parent_span_id is None

    def test_multi_header_with_parent(self):
        headers = {
            "X-B3-TraceId": "463ac35c9f6413ad48485a3953bb6124",
            "X-B3-SpanId": "0020000000000001",
            "X-B3-Sampled": "1",
            "X-B3-ParentSpanId": "0010000000000001",
        }
        data = extract_b3(headers)
        assert data.parent_span_id == "0010000000000001"

    def test_multi_header_not_sampled(self):
        headers = {
            "X-B3-TraceId": "aaa",
            "X-B3-SpanId": "bbb",
            "X-B3-Sampled": "0",
        }
        data = extract_b3(headers)
        assert data.sampled is False

    def test_single_header_basic(self):
        headers = {"b3": "80f198ee56343ba864fe8b2a57d3eff7-e457b5a2e4d86bd1-1"}
        data = extract_b3(headers)
        assert data is not None
        assert data.trace_id == "80f198ee56343ba864fe8b2a57d3eff7"
        assert data.span_id == "e457b5a2e4d86bd1"
        assert data.sampled is True

    def test_single_header_with_parent(self):
        headers = {"b3": "80f198ee56343ba864fe8b2a57d3eff7-e457b5a2e4d86bd1-1-05e3ac9a4f6e3b90"}
        data = extract_b3(headers)
        assert data.parent_span_id == "05e3ac9a4f6e3b90"

    def test_single_header_deny(self):
        """'0' means deny — no sampling."""
        headers = {"b3": "0"}
        data = extract_b3(headers)
        assert data is not None
        assert data.sampled is False

    def test_single_header_accept(self):
        """'1' means accept but no context."""
        headers = {"b3": "1"}
        data = extract_b3(headers)
        assert data is None  # Accept but no trace context to extract

    def test_single_header_debug(self):
        """'d' means debug — accept but no context."""
        headers = {"b3": "d"}
        data = extract_b3(headers)
        assert data is None

    def test_empty_headers(self):
        data = extract_b3({})
        assert data is None

    def test_missing_span_id(self):
        """Multi-header requires both trace and span IDs."""
        headers = {"X-B3-TraceId": "abc"}
        data = extract_b3(headers)
        assert data is None

    def test_single_header_too_short(self):
        headers = {"b3": "abc"}
        data = extract_b3(headers)
        assert data is None


class TestB3Inject:
    def test_no_context_no_injection(self):
        """Without active trace, inject should not add B3 headers."""
        headers = {}
        result = inject_b3(headers)
        assert "X-B3-TraceId" not in result
        assert "b3" not in result

    def test_preserves_existing_headers(self):
        headers = {"Authorization": "Bearer token"}
        result = inject_b3(headers)
        assert result["Authorization"] == "Bearer token"


class TestB3TraceContextData:
    def test_attributes(self):
        data = B3TraceContextData(
            trace_id="abc",
            span_id="def",
            sampled=True,
            parent_span_id="ghi",
        )
        assert data.trace_id == "abc"
        assert data.span_id == "def"
        assert data.sampled is True
        assert data.parent_span_id == "ghi"

    def test_defaults(self):
        data = B3TraceContextData(trace_id="a", span_id="b")
        assert data.sampled is True
        assert data.parent_span_id is None
