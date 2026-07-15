"""Unit tests for the Trace Diffing engine."""

from agent_tracer_plus.core.models import Span, Trace, SpanType
from agent_tracer_plus.intelligence.diff import diff_traces


def test_trace_diff_sequence_alignment():
    # Base Trace: Think -> Tool A -> Think -> Final
    t_a = Trace(trace_id="t1")
    s_a1 = Span(name="think", span_id="s1", trace_id="t1", span_type=SpanType.LLM, started_at=1)
    s_a2 = Span(name="tool_a", span_id="s2", trace_id="t1", span_type=SpanType.TOOL, started_at=2)
    s_a3 = Span(name="think", span_id="s3", trace_id="t1", span_type=SpanType.LLM, started_at=3)
    s_a4 = Span(name="final", span_id="s4", trace_id="t1", span_type=SpanType.CUSTOM, started_at=4)
    base_spans = [s_a1, s_a2, s_a3, s_a4]

    # Compare Trace: Think -> Tool B -> Final (skipped second think)
    t_b = Trace(trace_id="t2")
    s_b1 = Span(name="think", span_id="s5", trace_id="t2", span_type=SpanType.LLM, started_at=1)
    s_b2 = Span(name="tool_b", span_id="s6", trace_id="t2", span_type=SpanType.TOOL, started_at=2)
    s_b3 = Span(name="final", span_id="s7", trace_id="t2", span_type=SpanType.CUSTOM, started_at=3)
    compare_spans = [s_b1, s_b2, s_b3]

    report = diff_traces(t_a, base_spans, t_b, compare_spans)

    assert report.reasoning_path_changed is True
    ops = report.span_ops
    
    # Expected alignment:
    # equal (think)
    # replace (tool_a -> tool_b)
    # delete (think)
    # equal (final)
    
    # Depending on difflib exact alignment, the delete and replace might be ordered differently
    # Let's check that we have exactly one of each operation type roughly
    opcodes = [op.opcode for op in ops]
    assert opcodes.count("equal") == 2
    assert opcodes.count("replace") == 1
    assert opcodes.count("delete") == 1


def test_trace_diff_text_diffing():
    t_a = Trace(trace_id="t1")
    s_a1 = Span(name="think", span_id="s1", trace_id="t1", span_type=SpanType.LLM, started_at=1)
    s_a1.input = "This is the original prompt.\nIt has two lines."
    base_spans = [s_a1]

    t_b = Trace(trace_id="t2")
    s_b1 = Span(name="think", span_id="s2", trace_id="t2", span_type=SpanType.LLM, started_at=1)
    s_b1.input = "This is the modified prompt.\nIt has two lines."
    compare_spans = [s_b1]

    report = diff_traces(t_a, base_spans, t_b, compare_spans)
    
    assert len(report.span_ops) == 1
    op = report.span_ops[0]
    
    assert op.opcode == "equal"
    assert op.input_changed is True
    assert "modified prompt" in op.input_diff
    assert "original prompt" in op.input_diff
