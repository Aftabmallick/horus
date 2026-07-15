
import pytest

from agent_tracer_plus import init, trace_agent, trace_step
from agent_tracer_plus.storage.memory import InMemoryBackend


@pytest.mark.asyncio
async def test_full_trace_lifecycle():
    # 1. Initialize tracer with in-memory backend
    tracer = init(storage="memory://", service_name="e2e-test", force=True)

    @trace_step(name="fetch_data")
    async def fetch_data(query: str):
        return f"data for {query}"

    @trace_agent(name="E2EAgent")
    async def e2e_agent(query: str):
        data = await fetch_data(query)
        return f"Processed {data}"

    # 2. Run agent
    result = await e2e_agent("hello")
    assert result == "Processed data for hello"

    # 3. Flush
    await tracer.flush()

    # 4. Verify storage
    memory_backend: InMemoryBackend = tracer.storage # type: ignore

    traces = [t for t in memory_backend.get_all_traces() if t["service_name"] == "e2e-test"]
    assert len(traces) == 1

    trace_data = traces[0]
    assert trace_data["agent_name"] == "E2EAgent"
    assert trace_data["status"] == "COMPLETED"

    spans = [s for s in memory_backend.get_all_spans() if s["service_name"] == "e2e-test"]
    assert len(spans) == 2

    # Check parent/child relationship
    agent_span = next(s for s in spans if s["span_type"] == "AGENT")
    step_span = next(s for s in spans if s["span_type"] == "CHAIN")

    assert agent_span["name"] == "E2EAgent"
    assert step_span["name"] == "fetch_data"
    assert step_span["parent_span_id"] == agent_span["span_id"]
    assert step_span["trace_id"] == agent_span["trace_id"]
