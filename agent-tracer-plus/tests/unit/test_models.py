from agent_tracer_plus.core.models import CostInfo, Span, TokenUsage, Trace


def test_trace_creation():
    trace = Trace(agent_name="TestAgent")
    assert trace.trace_id is not None
    assert trace.execution_id is not None
    assert trace.status == "RUNNING"
    assert trace.agent_name == "TestAgent"

def test_span_hierarchy():
    trace = Trace()
    parent = Span(name="parent")
    trace.add_span(parent)

    child = Span(name="child", parent_span_id=parent.span_id)
    trace.add_span(child)

    assert child.trace_id == trace.trace_id
    assert child.parent_span_id == parent.span_id

def test_metrics_aggregation():
    trace = Trace()

    span1 = Span(name="llm1", token_usage=TokenUsage(input_tokens=10, output_tokens=20), cost_info=CostInfo(total_cost=0.05))
    span2 = Span(name="llm2", token_usage=TokenUsage(input_tokens=5, output_tokens=10), cost_info=CostInfo(total_cost=0.02))

    trace.add_span(span1)
    trace.add_span(span2)

    trace.finish()

    assert trace.span_count == 2
    assert trace.total_tokens == 45
    assert trace.total_cost == 0.07
    assert trace.status == "COMPLETED"
