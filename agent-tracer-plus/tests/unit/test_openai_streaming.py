import pytest
pytest.importorskip("openai")
import asyncio
from unittest.mock import patch, MagicMock
from agent_tracer_plus import init
from agent_tracer_plus.core.context import _current_trace, _current_span

class MockUsage:
    def __init__(self, prompt_tokens, completion_tokens):
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = prompt_tokens + completion_tokens

class MockDelta:
    def __init__(self, content):
        self.content = content

class MockChoice:
    def __init__(self, content):
        self.delta = MockDelta(content)

class MockChunk:
    def __init__(self, content, usage=None):
        self.choices = [MockChoice(content)] if content is not None else []
        self.usage = usage

import os

@pytest.mark.asyncio
async def test_openai_async_stream_span_captures_tokens():
    os.environ["AGENT_TRACER_PLUS_ENABLED"] = "1"
    _current_trace.set(None)
    _current_span.set(None)
    tracer = init(storage="memory://", auto_instrument=False, force=True, enabled=True)
    
    # Mock streaming response with usage in final chunk
    async def mock_stream():
        yield MockChunk(content="Hello", usage=None)
        yield MockChunk(content=" world", usage=None)
        yield MockChunk(content=None, usage=MockUsage(prompt_tokens=10, completion_tokens=5))
    
    import openai
    from agent_tracer_plus.auto.openai_instr import _wrap_async
    
    with patch("openai.resources.chat.completions.AsyncCompletions.create") as mock:
        async def mock_create(*args, **kwargs):
            return mock_stream()
        mock.side_effect = mock_create
        
        # Explicitly wrap the mock so we get span logic regardless of global patch state
        openai.resources.chat.completions.AsyncCompletions.create = _wrap_async(mock)
        
        client = openai.AsyncOpenAI(api_key="test")
        
        from agent_tracer_plus.core.context import TraceContext
        with TraceContext():
            assembled = []
            async for chunk in await client.chat.completions.create(model="gpt-4o-mini", messages=[], stream=True):
                if chunk.choices and chunk.choices[0].delta.content:
                    assembled.append(chunk.choices[0].delta.content)
                    
            assert "".join(assembled) == "Hello world"
    
    import asyncio
    await asyncio.sleep(0.01)
    await tracer.flush()
    
    spans = tracer.storage.get_all_spans()
    llm_span = next((s for s in spans if s["span_type"] == "LLM"), None)
    
    assert llm_span is not None, "LLM Span not found"
    assert llm_span["token_usage"]["total_tokens"] == 15
    assert llm_span["cost_info"]["total_cost"] > 0
    assert "Hello world" in str(llm_span["output"])
