import pytest
from unittest.mock import patch, MagicMock
from agent_tracer_plus import init, trace_agent

@pytest.mark.asyncio
async def test_aiohttp_patch_injects_w3c_header():
    class MockResponse:
        def __init__(self, status):
            self.status = status
            
    import aiohttp
    with patch("aiohttp.ClientSession._request") as mock_req:
        mock_req.return_value = MockResponse(200)
        
        import agent_tracer_plus.auto.http_instr as http_instr
        http_instr._AIOHTTP_PATCHED = False
        tracer = init(storage="memory://", force=True)
        http_instr.patch_aiohttp()
        
        captured_headers = {}
        
        @trace_agent(name="TestAgent")
        async def agent():
            async with aiohttp.ClientSession() as session:
                await session.get("http://example.com")
            
            call_kwargs = mock_req.call_args[1]
            captured_headers.update(call_kwargs.get("headers", {}))
            
        await agent()
        
    assert "traceparent" in captured_headers
    tp = captured_headers["traceparent"]
    assert tp.startswith("00-")
    assert len(tp.split("-")) == 4
