"""E2E test: W3C traceparent header is injected into HTTP calls."""
import pytest
from unittest.mock import patch, MagicMock
import agent_tracer_plus
from agent_tracer_plus import trace_agent

@pytest.mark.asyncio
async def test_w3c_header_injected_in_httpx():
    tracer = agent_tracer_plus.init(
        storage="memory://", auto_instrument=True, force=True
    )
    
    captured_headers = {}
    
    @trace_agent(name="HttpAgent")
    async def agent():
        import httpx
        def handler(request):
            captured_headers.update(dict(request.headers))
            return httpx.Response(200, request=request)
            
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            resp = await client.get("https://example.com")
            
    await agent()
    assert "traceparent" in captured_headers, "W3C traceparent header must be injected"
    
    tp = captured_headers["traceparent"]
    parts = tp.split("-")
    assert len(parts) == 4, f"traceparent must have 4 parts: {tp}"
    assert parts[0] == "00"
    assert len(parts[1]) == 32, f"trace-id must be 32 hex chars: {parts[1]}"
    assert len(parts[2]) == 16, f"span-id must be 16 hex chars: {parts[2]}"
