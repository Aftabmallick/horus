"""Comprehensive tests for context propagation — TraceContext, SpanContext, thread propagation."""

import asyncio
import concurrent.futures

import pytest

from agent_tracer_plus.core.context import (
    SpanContext,
    TraceContext,
    get_current_span,
    get_current_trace,
    propagate_context,
)
from agent_tracer_plus.core.models import SpanStatus, SpanType, TraceStatus


class TestTraceContext:
    def test_basic_lifecycle(self):
        assert get_current_trace() is None
        with TraceContext(agent_name="Agent") as trace:
            assert get_current_trace() is trace
            assert trace.agent_name == "Agent"
        assert get_current_trace() is None

    def test_trace_finishes_on_exit(self):
        with TraceContext(agent_name="A") as trace:
            pass
        assert trace.ended_at is not None
        assert trace.status in (TraceStatus.COMPLETED, TraceStatus.ERROR)

    def test_trace_error_on_exception(self):
        with pytest.raises(ValueError):
            with TraceContext(agent_name="ErrAgent") as trace:
                raise ValueError("boom")
        assert trace.status == TraceStatus.ERROR

    def test_metadata_and_tags(self):
        with TraceContext(agent_name="M", metadata={"k": "v"}, tags=["t1"]) as trace:
            assert trace.metadata == {"k": "v"}
            assert trace.tags == ["t1"]


class TestSpanContext:
    def test_basic_lifecycle(self):
        assert get_current_span() is None
        with TraceContext(agent_name="T"):
            with SpanContext(name="step1") as span:
                assert get_current_span() is span
                assert span.name == "step1"
            assert get_current_span() is None

    def test_span_links_to_trace(self):
        with TraceContext(agent_name="T") as trace:
            with SpanContext(name="s") as span:
                assert span.trace_id == trace.trace_id

    def test_nested_span_parent_chain(self):
        with TraceContext(agent_name="T"):
            with SpanContext(name="parent") as parent:
                assert parent.parent_span_id is None
                with SpanContext(name="child") as child:
                    assert child.parent_span_id == parent.span_id
                    with SpanContext(name="grandchild") as gc:
                        assert gc.parent_span_id == child.span_id
                    assert get_current_span() is child
                assert get_current_span() is parent

    def test_span_restores_parent_after_exit(self):
        with TraceContext(agent_name="T"):
            with SpanContext(name="p") as parent:
                with SpanContext(name="c") as child:
                    pass
                # After child exits, current span should be parent
                assert get_current_span() is parent

    def test_span_error_on_exception(self):
        with TraceContext(agent_name="T"):
            with pytest.raises(RuntimeError):
                with SpanContext(name="fail") as span:
                    raise RuntimeError("fail")
            assert span.status == SpanStatus.ERROR

    def test_span_finishes_ok(self):
        with TraceContext(agent_name="T"):
            with SpanContext(name="ok") as span:
                pass
        assert span.status == SpanStatus.OK
        assert span.ended_at is not None

    def test_span_type(self):
        with TraceContext(agent_name="T"):
            with SpanContext(name="llm_call", span_type=SpanType.LLM) as span:
                pass
            assert span.span_type == SpanType.LLM

    def test_span_attributes(self):
        with TraceContext(agent_name="T"):
            with SpanContext(name="s", attributes={"key": "val"}) as span:
                pass
            assert span.attributes["key"] == "val"

    def test_spans_registered_on_trace(self):
        with TraceContext(agent_name="T") as trace:
            with SpanContext(name="s1"):
                pass
            with SpanContext(name="s2"):
                pass
        assert len(trace.spans) == 2
        assert trace.spans[0].name == "s1"
        assert trace.spans[1].name == "s2"


class TestPropagateContext:
    def test_propagates_to_thread(self):
        """propagate_context should carry trace context to a thread pool worker."""
        captured_trace_id = None

        with TraceContext(agent_name="ThreadTest") as trace:
            def worker():
                nonlocal captured_trace_id
                current = get_current_trace()
                captured_trace_id = current.trace_id if current else None

            wrapped = propagate_context(worker)

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(wrapped)
                future.result()

        assert captured_trace_id == trace.trace_id

    def test_no_leak_without_propagation(self):
        """Without propagate_context, thread pool workers should not see the trace."""
        captured_trace_id = "NOT_NONE"  # sentinel

        with TraceContext(agent_name="NoLeak"):
            def worker():
                nonlocal captured_trace_id
                current = get_current_trace()
                captured_trace_id = current.trace_id if current else None

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(worker)
                future.result()

        assert captured_trace_id is None
