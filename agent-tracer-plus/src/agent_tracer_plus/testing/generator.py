"""Trace-to-Test Pipeline: Generates pytest files from production traces."""

import os
from typing import List

from agent_tracer_plus.core.models import Trace, Span, SpanType


def generate_pytest_file(trace: Trace, spans: List[Span], output_dir: str = "tests/generated") -> str:
    """Generate a valid pytest file using unittest.mock to mock tool responses."""
    os.makedirs(output_dir, exist_ok=True)
    
    file_path = os.path.join(output_dir, f"test_trace_{trace.trace_id}.py")
    
    # Group spans
    llm_spans = [s for s in spans if s.span_type == SpanType.LLM]
    tool_spans = [s for s in spans if s.span_type in (SpanType.TOOL, SpanType.RETRIEVAL)]
    
    lines = [
        '"""Auto-generated pytest file from production trace."""',
        "",
        "import pytest",
        "from unittest.mock import patch, MagicMock",
        "",
        "@pytest.mark.asyncio",
        f"async def test_trace_{trace.trace_id.replace('-', '_')}():",
        f"    # Agent: {trace.agent_name}",
        f"    # Original Duration: {trace.duration_ms}ms",
        f"    # Original Cost: ${trace.total_cost}",
        ""
    ]
    
    if tool_spans:
        lines.append("    # --- Mocked Tools ---")
        for i, tool in enumerate(tool_spans):
            safe_name = tool.name.replace(".", "_")
            # We mock the return value
            output_val = tool.output if tool.output else ""
            lines.append(f"    mock_{safe_name}_{i} = MagicMock(return_value={repr(output_val)})")
            lines.append(f"    patcher_{i} = patch('{tool.name}', mock_{safe_name}_{i})")
            lines.append(f"    patcher_{i}.start()")
        lines.append("")
        
    lines.append("    # --- Execution ---")
    lines.append("    # TODO: Import and call your actual agent/function here.")
    lines.append("    # result = await my_agent_function(...)")
    lines.append("    result = None")
    lines.append("")
    
    lines.append("    # --- Assertions ---")
    if llm_spans:
        for llm in llm_spans:
            lines.append(f"    # Assert LLM generated something similar to this:")
            lines.append(f"    # expected_output = {repr(llm.output)}")
            lines.append("    # assert expected_output in result")
    else:
        lines.append("    assert True")
        
    if tool_spans:
        lines.append("")
        lines.append("    # Cleanup mocks")
        for i in range(len(tool_spans)):
            lines.append(f"    patcher_{i}.stop()")
            
    lines.append("")
    
    with open(file_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
        
    return file_path
