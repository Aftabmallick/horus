import pytest
from agent_tracer_plus.propagation.w3c import W3CTraceContextPropagator, TraceContextData, extract_context, inject_context
from agent_tracer_plus.core.context import SpanContext, get_current_trace
from agent_tracer_plus.core.models import SpanType

def test_extract_context_valid():
    headers = {"traceparent": "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"}
    ctx = extract_context(headers)
    assert ctx is not None
    assert ctx.trace_id == "4bf92f3577b34da6a3ce929d0e0e4736"
    assert ctx.span_id == "00f067aa0ba902b7"
    assert ctx.trace_flags == 1

def test_extract_context_invalid():
    headers = {"traceparent": "invalid-traceparent-string"}
    ctx = extract_context(headers)
    assert ctx is None

def test_inject_context_creates_valid_header():
    from agent_tracer_plus import init
    import os
    os.environ["AGENT_TRACER_PLUS_ENABLED"] = "1"
    tracer = init(storage="memory://", force=True, enabled=True)
    from agent_tracer_plus.core.context import TraceContext, SpanContext, SpanType
    with TraceContext() as trace:
        with SpanContext(name="test", span_type=SpanType.AGENT) as span:
            headers = {}
            inject_context(headers)
            assert "traceparent" in headers
        
        # Verify it can be extracted back
        ctx = extract_context(headers)
        assert ctx is not None
        
        # Verify dashes were stripped
        trace = get_current_trace()
        assert trace.trace_id.replace("-", "")[:32].ljust(32, "0") == ctx.trace_id
        assert span.span_id.replace("-", "")[:16].ljust(16, "0") == ctx.span_id
