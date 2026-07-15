from pathlib import Path

import pytest

from agent_tracer_plus.core.models import Span, Trace
from agent_tracer_plus.testing.golden import GoldenTrace


def test_golden_trace_save_load(tmp_path: Path):
    trace = Trace(trace_id="test_golden")
    span = Span(name="step_1", trace_id="test_golden")
    span.output = "golden output"

    golden = GoldenTrace(trace, [span], name="baseline_1")
    golden.save(tmp_path)

    loaded = GoldenTrace.load(tmp_path / "baseline_1.json")
    assert loaded.trace.trace_id == "test_golden"
    assert len(loaded.spans) == 1
    assert loaded.spans[0].output == "golden output"

def test_golden_trace_assert_matches():
    trace = Trace(trace_id="t1")
    span1 = Span(name="step_1", trace_id="t1", output="A")
    span2 = Span(name="step_2", trace_id="t1", output="B")

    golden = GoldenTrace(trace, [span1, span2], name="base")

    # Matching exactly
    golden.assert_matches([span1, span2], strict=True)

    # Order mismatch but chronological sorting should fix if timestamps exist
    # If same timestamp (like in this quick test), order matters.
    # Let's adjust timestamps to ensure sorting works.
    import time
    span1.started_at = trace.started_at
    time.sleep(0.01)
    span2.started_at = trace.started_at

    # Different output fails in strict mode
    span2_diff = Span(name="step_2", trace_id="t1", output="C")
    span2_diff.started_at = span2.started_at

    with pytest.raises(AssertionError, match="Output mismatch"):
        golden.assert_matches([span1, span2_diff], strict=True)

    # Different output succeeds in non-strict mode
    golden.assert_matches([span1, span2_diff], strict=False)
