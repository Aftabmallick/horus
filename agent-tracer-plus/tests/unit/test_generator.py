"""Unit tests for the Trace-to-Test pipeline."""

import os
import pytest
from agent_tracer_plus.core.models import Trace, Span, SpanType
from agent_tracer_plus.testing.generator import generate_pytest_file


def test_generate_pytest_file(tmp_path):
    trace = Trace(trace_id="test_123", agent_name="TestAgent")
    
    s1 = Span(name="my_tool", span_type=SpanType.TOOL, output="Tool Response")
    s2 = Span(name="llm_call", span_type=SpanType.LLM, output="LLM Response")
    
    out_dir = str(tmp_path / "generated")
    file_path = generate_pytest_file(trace, [s1, s2], output_dir=out_dir)
    
    assert os.path.exists(file_path)
    
    with open(file_path, "r") as f:
        content = f.read()
        
    assert "async def test_trace_test_123():" in content
    assert "mock_my_tool_0 = MagicMock(return_value='Tool Response')" in content
    assert "patcher_0 = patch('my_tool', mock_my_tool_0)" in content
    assert "expected_output = 'LLM Response'" in content
