"""Comprehensive tests for core data models: Trace, Span, Event, SpanLink, TokenUsage, CostInfo."""

import pytest
from datetime import datetime, timezone

from agent_tracer_plus.core.models import (
    CostInfo,
    Event,
    Span,
    SpanLink,
    SpanStatus,
    SpanType,
    TokenUsage,
    Trace,
    TraceStatus,
)


# ── TokenUsage ─────────────────────────────────────────────────────────────


class TestTokenUsage:
    def test_auto_total(self):
        usage = TokenUsage(input_tokens=100, output_tokens=50)
        assert usage.total_tokens == 150

    def test_explicit_total(self):
        usage = TokenUsage(input_tokens=100, output_tokens=50, total_tokens=200)
        assert usage.total_tokens == 200

    def test_zero_defaults(self):
        usage = TokenUsage()
        assert usage.input_tokens == 0
        assert usage.output_tokens == 0
        assert usage.total_tokens == 0
        assert usage.cached_tokens == 0


# ── CostInfo ───────────────────────────────────────────────────────────────


class TestCostInfo:
    def test_auto_total(self):
        cost = CostInfo(input_cost=0.01, output_cost=0.02)
        assert cost.total_cost == pytest.approx(0.03)

    def test_explicit_total(self):
        cost = CostInfo(input_cost=0.01, output_cost=0.02, total_cost=0.05)
        assert cost.total_cost == pytest.approx(0.05)

    def test_model_and_source(self):
        cost = CostInfo(total_cost=0.10, model="gpt-4o", pricing_source="auto")
        assert cost.model == "gpt-4o"
        assert cost.pricing_source == "auto"


# ── SpanLink ───────────────────────────────────────────────────────────────


class TestSpanLink:
    def test_defaults(self):
        link = SpanLink(linked_trace_id="t1", linked_span_id="s1")
        assert link.link_type == "child_of"
        assert link.attributes == {}

    def test_custom_type(self):
        link = SpanLink(linked_trace_id="t1", linked_span_id="s1", link_type="follows_from")
        assert link.link_type == "follows_from"


# ── Event ──────────────────────────────────────────────────────────────────


class TestEvent:
    def test_creation(self):
        event = Event(name="checkpoint")
        assert event.name == "checkpoint"
        assert isinstance(event.timestamp, datetime)
        assert event.event_id

    def test_to_dict(self):
        event = Event(name="test", attributes={"key": "value"})
        d = event.to_dict()
        assert d["name"] == "test"
        assert d["attributes"]["key"] == "value"
        assert "timestamp" in d
        assert "event_id" in d


# ── Span ───────────────────────────────────────────────────────────────────


class TestSpan:
    def test_creation_defaults(self):
        span = Span(name="test_span")
        assert span.name == "test_span"
        assert span.span_type == SpanType.CUSTOM
        assert span.status == SpanStatus.RUNNING
        assert span.span_id  # not empty
        assert span.parent_span_id is None
        assert span.input is None
        assert span.output is None

    def test_set_attribute(self):
        span = Span(name="s")
        span.set_attribute("key", "value")
        assert span.attributes["key"] == "value"

    def test_set_output(self):
        span = Span(name="s")
        span.set_output({"result": 42})
        assert span.output == {"result": 42}

    def test_set_error(self):
        span = Span(name="s")
        span.set_error(ValueError("bad input"))
        assert span.status == SpanStatus.ERROR
        assert span.error["type"] == "ValueError"
        assert span.error["message"] == "bad input"
        assert span.error["module"] == "builtins"

    def test_add_event(self):
        span = Span(name="s")
        event = span.add_event("checkpoint", {"progress": 50})
        assert len(span.events) == 1
        assert event.name == "checkpoint"
        assert event.attributes["progress"] == 50

    def test_add_link(self):
        span = Span(name="s")
        link = span.add_link("trace_2", "span_2", link_type="follows_from")
        assert len(span.links) == 1
        assert link.linked_trace_id == "trace_2"

    def test_finish_sets_status_ok(self):
        span = Span(name="s")
        span.finish()
        assert span.status == SpanStatus.OK
        assert span.ended_at is not None

    def test_finish_preserves_error_status(self):
        span = Span(name="s")
        span.set_error(RuntimeError("fail"))
        span.finish()
        assert span.status == SpanStatus.ERROR

    def test_finish_explicit_status(self):
        span = Span(name="s")
        span.finish(status=SpanStatus.CANCELLED)
        assert span.status == SpanStatus.CANCELLED

    def test_to_dict_basic(self):
        span = Span(name="test", span_type=SpanType.LLM, trace_id="t1", span_id="s1")
        span.finish()
        d = span.to_dict()
        assert d["name"] == "test"
        assert d["span_type"] == "LLM"
        assert d["trace_id"] == "t1"
        assert d["span_id"] == "s1"
        assert d["status"] == "OK"

    def test_to_dict_with_tokens(self):
        span = Span(name="s")
        span.token_usage = TokenUsage(input_tokens=10, output_tokens=20)
        span.cost_info = CostInfo(total_cost=0.05, model="gpt-4o")
        d = span.to_dict()
        assert d["token_usage"]["total_tokens"] == 30
        assert d["cost_info"]["model"] == "gpt-4o"

    def test_to_dict_with_input_output(self):
        span = Span(name="s")
        span.input = {"query": "hello"}
        span.output = {"answer": "world"}
        d = span.to_dict()
        assert d["input"]["query"] == "hello"
        assert d["output"]["answer"] == "world"

    def test_from_dict_roundtrip(self):
        span = Span(name="original", span_type=SpanType.TOOL, trace_id="t1", span_id="s1")
        span.set_attribute("key", "val")
        span.input = "input_data"
        span.output = "output_data"
        span.finish()
        d = span.to_dict()

        restored = Span.from_dict(d)
        assert restored.name == "original"
        assert restored.span_id == "s1"
        assert restored.trace_id == "t1"
        assert restored.status == SpanStatus.OK

    def test_from_dict_handles_empty_parent(self):
        """Protobuf sends empty strings for optional fields."""
        restored = Span.from_dict({"name": "s", "parent_span_id": ""})
        assert restored.parent_span_id is None

    def test_from_dict_invalid_span_type(self):
        restored = Span.from_dict({"name": "s", "span_type": "NONEXISTENT"})
        assert restored.span_type == SpanType.CUSTOM

    def test_from_dict_calculates_duration(self):
        restored = Span.from_dict({
            "name": "s",
            "started_at": "2026-01-01T00:00:00+00:00",
            "ended_at": "2026-01-01T00:00:01+00:00",
            "duration_ms": 0,
        })
        assert restored.duration_ms == pytest.approx(1000.0)


# ── Trace ──────────────────────────────────────────────────────────────────


class TestTrace:
    def test_creation_defaults(self):
        trace = Trace()
        assert trace.trace_id  # not empty
        assert trace.execution_id  # not empty
        assert trace.status == TraceStatus.RUNNING
        assert trace.spans == []

    def test_set_metadata(self):
        trace = Trace()
        trace.set_metadata({"user_id": "u1"})
        trace.set_metadata({"session": "s1"})
        assert trace.metadata["user_id"] == "u1"
        assert trace.metadata["session"] == "s1"

    def test_add_tag(self):
        trace = Trace()
        trace.add_tag("important")
        trace.add_tag("important")  # duplicate
        trace.add_tag("debug")
        assert trace.tags == ["important", "debug"]

    def test_add_span(self):
        trace = Trace(service_name="my-svc")
        span = Span(name="s1")
        trace.add_span(span)
        assert span.trace_id == trace.trace_id
        assert span.service_name == "my-svc"
        assert len(trace.spans) == 1

    def test_finish_aggregates_metrics(self):
        trace = Trace()
        s1 = Span(name="llm1", token_usage=TokenUsage(input_tokens=100, output_tokens=50))
        s1.cost_info = CostInfo(total_cost=0.10)
        s2 = Span(name="llm2", token_usage=TokenUsage(input_tokens=200, output_tokens=100))
        s2.cost_info = CostInfo(total_cost=0.20)
        s3 = Span(name="error_span")
        s3.set_error(RuntimeError("fail"))
        trace.add_span(s1)
        trace.add_span(s2)
        trace.add_span(s3)
        trace.finish()

        assert trace.span_count == 3
        assert trace.total_tokens == 450
        assert trace.total_cost == pytest.approx(0.30)
        assert trace.error_count == 1
        assert trace.status == TraceStatus.ERROR

    def test_finish_status_completed(self):
        trace = Trace()
        span = Span(name="ok")
        trace.add_span(span)
        trace.finish()
        assert trace.status == TraceStatus.COMPLETED

    def test_finish_explicit_status(self):
        trace = Trace()
        trace.finish(status=TraceStatus.CANCELLED)
        assert trace.status == TraceStatus.CANCELLED

    def test_to_dict(self):
        trace = Trace(agent_name="TestAgent", service_name="svc")
        trace.finish()
        d = trace.to_dict()
        assert d["agent_name"] == "TestAgent"
        assert d["service_name"] == "svc"
        assert d["status"] == "COMPLETED"
        assert "trace_id" in d

    def test_from_dict_roundtrip(self):
        trace = Trace(agent_name="Test", service_name="svc", tenant_id="t1")
        trace.set_metadata({"key": "value"})
        trace.add_tag("tag1")
        trace.finish()
        d = trace.to_dict()

        restored = Trace.from_dict(d)
        assert restored.trace_id == trace.trace_id
        assert restored.agent_name == "Test"
        assert restored.service_name == "svc"
        assert restored.tenant_id == "t1"
        assert restored.metadata == {"key": "value"}
        assert restored.tags == ["tag1"]
        assert restored.status == TraceStatus.COMPLETED

    def test_from_dict_invalid_status(self):
        restored = Trace.from_dict({"status": "INVALID_STATUS"})
        assert restored.status == TraceStatus.RUNNING
