from unittest.mock import AsyncMock, patch

import pytest

from agent_tracer_plus.core.models import Span, SpanStatus, Trace
from agent_tracer_plus.intelligence.diagnosis import TraceDiagnoser


@pytest.mark.asyncio
async def test_trace_diagnoser_success_skip():
    # If trace has no errors, it skips LLM call
    trace = Trace(trace_id="t_ok", status=SpanStatus.OK)
    spans = [Span(name="step_1", status=SpanStatus.OK)]

    diagnoser = TraceDiagnoser(api_key="fake")
    result = await diagnoser.diagnose(trace, spans)

    assert result["status"] == "ok"
    assert "No errors found" in result["diagnosis"]

@pytest.mark.asyncio
@patch.dict('sys.modules', {'litellm': __import__('unittest.mock').mock.MagicMock()})
@patch('agent_tracer_plus.intelligence.diagnosis.SemanticSearcher')
async def test_trace_diagnoser_with_error(mock_searcher_class):
    import sys
    mock_litellm = sys.modules['litellm']

    mock_response = AsyncMock()
    mock_response.choices = [AsyncMock()]
    mock_response.choices[0].message.content = "Root cause: Tool failed."
    mock_litellm.acompletion = AsyncMock(return_value=mock_response)

    # Mock SemanticSearcher to avoid sentence-transformers dependency
    mock_searcher_instance = AsyncMock()
    mock_searcher_instance.search.return_value = []
    mock_searcher_class.return_value = mock_searcher_instance

    trace = Trace(trace_id="t_err", status=SpanStatus.ERROR)
    span_err = Span(name="db_query", status=SpanStatus.ERROR, error={"message": "Timeout"})

    diagnoser = TraceDiagnoser(api_key="fake")
    result = await diagnoser.diagnose(trace, [span_err])

    assert result["status"] == "diagnosed"
    assert result["diagnosis"] == "Root cause: Tool failed."

    # Verify formatting output
    formatted = diagnoser._format_trace_for_llm(trace, [span_err])
    assert "Trace ID: t_err" in formatted
    assert "db_query" in formatted
    assert "Timeout" in formatted
