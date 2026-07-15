from agent_tracer_plus.core.context import (
    SpanContext,
    TraceContext,
    get_current_span,
    get_current_trace,
)


def test_trace_context():
    assert get_current_trace() is None

    with TraceContext(agent_name="CtxAgent") as trace:
        assert get_current_trace() is trace
        assert trace.agent_name == "CtxAgent"

        with SpanContext(name="step1") as span:
            assert get_current_span() is span
            assert span.trace_id == trace.trace_id
            assert span.parent_span_id is None

            with SpanContext(name="step2") as child:
                assert get_current_span() is child
                assert child.parent_span_id == span.span_id

            assert get_current_span() is span

    assert get_current_trace() is None
