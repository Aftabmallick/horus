import pytest
pytest.importorskip("anthropic")
import asyncio
from unittest.mock import patch, MagicMock
from agent_tracer_plus import init
from agent_tracer_plus.core.context import _current_trace, _current_span

class MockUsage:
    def __init__(self, input_tokens, output_tokens):
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens

class MockDelta:
    def __init__(self, text):
        self.text = text

class MockEvent:
    def __init__(self, text=None, usage=None):
        if text:
            self.delta = MockDelta(text)
        self.usage = usage

import os

@pytest.mark.asyncio
async def test_anthropic_async_stream_span_captures_tokens():
    os.environ["AGENT_TRACER_PLUS_ENABLED"] = "1"
    _current_trace.set(None)
    _current_span.set(None)
    tracer = init(storage="memory://", auto_instrument=False, force=True, enabled=True)
    
    async def mock_stream():
        yield MockEvent(text="Hello", usage=None)
        yield MockEvent(text=" anthropic", usage=None)
        yield MockEvent(text=None, usage=MockUsage(input_tokens=10, output_tokens=5))
    
    import anthropic
    from agent_tracer_plus.auto.anthropic_instr import _wrap_async
    
    with patch("anthropic.resources.messages.AsyncMessages.create") as mock:
        async def mock_create(*args, **kwargs):
            return mock_stream()
        mock.side_effect = mock_create
        
        # Explicitly wrap the mock so we get span logic regardless of global patch state
        anthropic.resources.messages.AsyncMessages.create = _wrap_async(mock)

        client = anthropic.AsyncAnthropic(api_key="test")
        
        from agent_tracer_plus.core.context import TraceContext
        with TraceContext():
            assembled = []
            async for event in await client.messages.create(model="claude-3-5-sonnet", messages=[], stream=True):
                if hasattr(event, "delta") and hasattr(event.delta, "text"):
                    assembled.append(event.delta.text)
                    
            assert "".join(assembled) == "Hello anthropic"
    
    import asyncio
    await asyncio.sleep(0.01)
    await tracer.flush()
    
    spans = tracer.storage.get_all_spans()
    llm_span = next((s for s in spans if s["span_type"] == "LLM"), None)
    
    assert llm_span is not None, "LLM Span not found"
    assert llm_span["token_usage"]["total_tokens"] == 15
    assert llm_span["cost_info"]["total_cost"] > 0
    assert "Hello anthropic" in llm_span["output"]
