import os
import pytest
from unittest import mock
from fastapi.testclient import TestClient

from agent_tracer_plus.core.models import Trace, Span, SpanType
from agent_tracer_plus.storage.memory import InMemoryBackend


@pytest.fixture
def override_ui_storage():
    os.environ["AGENT_TRACER_PLUS_UI_STORAGE"] = "memory://"
    yield
    del os.environ["AGENT_TRACER_PLUS_UI_STORAGE"]


def test_cli_ui_command():
    from agent_tracer_plus.cli.ui import run_ui
    
    with mock.patch("agent_tracer_plus.cli.ui.threading.Thread.start") as mock_thread:
        # Since uvicorn is imported inside the function, we mock sys.modules
        # or we can mock uvicorn.run directly
        with mock.patch("uvicorn.run") as mock_uvicorn:
            run_ui(port=9999, storage_uri="memory://")
            
            mock_thread.assert_called_once()
            mock_uvicorn.assert_called_once_with(
                "agent_tracer_plus.ui.server:app",
                host="127.0.0.1",
                port=9999,
                log_level="warning"
            )


@pytest.mark.asyncio
async def test_ui_api_endpoints(override_ui_storage):
    # Import inside test to ensure env var is picked up if needed, though FastAPI app is global
    from agent_tracer_plus.ui.server import app, get_storage
    
    # We must seed the memory storage
    storage = get_storage()
    assert isinstance(storage, InMemoryBackend)
    
    trace = Trace(trace_id="trace_ui_test")
    span = Span(span_id="s1", trace_id="trace_ui_test", name="test_span", span_type=SpanType.LLM)
    
    await storage.save_trace(trace)
    await storage.save_span(span)
    
    client = TestClient(app)
    
    # Test GET /api/traces
    resp = client.get("/api/traces")
    assert resp.status_code == 200
    data = resp.json()
    assert "traces" in data
    assert len(data["traces"]) == 1
    assert data["traces"][0]["trace_id"] == "trace_ui_test"
    
    # Test GET /api/traces/{trace_id}
    resp = client.get("/api/traces/trace_ui_test")
    assert resp.status_code == 200
    data = resp.json()
    assert data["trace"]["trace_id"] == "trace_ui_test"
    assert len(data["spans"]) == 1
    assert data["spans"][0]["span_id"] == "s1"
    
    # Test 404
    resp = client.get("/api/traces/unknown")
    assert resp.status_code == 404

    # Test GET / (index.html)
    resp = client.get("/")
    assert resp.status_code == 200
    assert "<title>Agent Tracer Plus - Local UI</title>" in resp.text
