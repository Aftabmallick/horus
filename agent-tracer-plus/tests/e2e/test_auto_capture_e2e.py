"""End-to-end test for the full auto-capture lifecycle.

Tests the complete pipeline: init → decorate → execute → flush → verify storage.
"""

import asyncio
import pytest

from agent_tracer_plus import init, trace_agent, trace_step, trace_tool, trace_llm
from agent_tracer_plus.core.context import get_current_trace, get_current_span
from agent_tracer_plus.core.models import SpanStatus, TokenUsage, CostInfo
from agent_tracer_plus.storage.memory import InMemoryBackend


class TestFullTraceLifecycle:
    @pytest.mark.asyncio
    async def test_basic_agent_with_steps(self):
        """Full lifecycle: init → agent → steps → flush → verify."""
        tracer = init(storage="memory://", service_name="e2e-test", auto_instrument=False, force=True)

        @trace_step(name="fetch")
        async def fetch_data(query: str):
            return f"data for {query}"

        @trace_step(name="process")
        async def process_data(data: str):
            return f"processed {data}"

        @trace_agent(name="PipelineAgent")
        async def run_pipeline(query: str):
            data = await fetch_data(query)
            result = await process_data(data)
            return result

        result = await run_pipeline("test_query")
        assert result == "processed data for test_query"

        await tracer.flush()

        backend: InMemoryBackend = tracer.storage  # type: ignore
        traces = backend.get_all_traces()
        assert len(traces) == 1

        trace_data = traces[0]
        assert trace_data["agent_name"] == "PipelineAgent"
        assert trace_data["status"] == "COMPLETED"
        assert trace_data["service_name"] == "e2e-test"

        spans = backend.get_all_spans()
        assert len(spans) == 3  # agent + fetch + process

        # Verify hierarchy
        agent_span = next(s for s in spans if s["name"] == "PipelineAgent")
        fetch_span = next(s for s in spans if s["name"] == "fetch")
        process_span = next(s for s in spans if s["name"] == "process")

        assert fetch_span["parent_span_id"] == agent_span["span_id"]
        assert process_span["parent_span_id"] == agent_span["span_id"]
        assert fetch_span["trace_id"] == agent_span["trace_id"]

    @pytest.mark.asyncio
    async def test_sync_agent(self):
        """Sync functions should also be traced correctly."""
        tracer = init(storage="memory://", service_name="sync-test", auto_instrument=False, force=True)

        @trace_step(name="sync_step")
        def my_step(x):
            return x * 2

        @trace_agent(name="SyncAgent")
        def my_agent(x):
            return my_step(x) + 1

        result = my_agent(5)
        assert result == 11

        await tracer.flush()

        backend: InMemoryBackend = tracer.storage  # type: ignore
        traces = [t for t in backend.get_all_traces() if t["service_name"] == "sync-test"]
        assert len(traces) == 1
        assert traces[0]["agent_name"] == "SyncAgent"

    @pytest.mark.asyncio
    async def test_error_trace(self):
        """Exceptions should be captured and trace marked as ERROR."""
        tracer = init(storage="memory://", service_name="err-test", auto_instrument=False, force=True)

        @trace_agent(name="ErrorAgent")
        async def failing_agent():
            raise RuntimeError("planned failure")

        with pytest.raises(RuntimeError, match="planned failure"):
            await failing_agent()

        await tracer.flush()

        backend: InMemoryBackend = tracer.storage  # type: ignore
        traces = [t for t in backend.get_all_traces() if t["service_name"] == "err-test"]
        assert len(traces) == 1
        assert traces[0]["status"] == "ERROR"

    @pytest.mark.asyncio
    async def test_nested_tool_and_llm(self):
        """Test tool and LLM decorators with correct span types."""
        tracer = init(storage="memory://", service_name="nested-test", auto_instrument=False, force=True)

        @trace_tool(name="search")
        async def search_tool(query):
            return f"results for {query}"

        @trace_llm(name="generate")
        async def llm_generate(prompt):
            return f"response to {prompt}"

        @trace_agent(name="MultiAgent")
        async def multi_agent(query):
            results = await search_tool(query)
            response = await llm_generate(f"summarize {results}")
            return response

        result = await multi_agent("weather")
        assert "response to" in result

        await tracer.flush()

        backend: InMemoryBackend = tracer.storage  # type: ignore
        spans = [s for s in backend.get_all_spans() if s["service_name"] == "nested-test"]
        assert len(spans) == 3

        tool_span = next(s for s in spans if s["name"] == "search")
        llm_span = next(s for s in spans if s["name"] == "generate")
        assert tool_span["span_type"] == "TOOL"
        assert llm_span["span_type"] == "LLM"

    @pytest.mark.asyncio
    async def test_context_cleanup(self):
        """After execution, trace context should be fully cleaned up."""
        tracer = init(storage="memory://", service_name="cleanup-test", auto_instrument=False, force=True)

        @trace_agent(name="CleanupAgent")
        async def agent():
            return "done"

        await agent()
        assert get_current_trace() is None
        assert get_current_span() is None

    @pytest.mark.asyncio
    async def test_multiple_sequential_runs(self):
        """Multiple agent runs should create separate traces."""
        tracer = init(storage="memory://", service_name="multi-test", auto_instrument=False, force=True)

        @trace_agent(name="RepeatAgent")
        async def agent(x):
            return x

        await agent(1)
        await agent(2)
        await agent(3)

        await tracer.flush()

        backend: InMemoryBackend = tracer.storage  # type: ignore
        traces = [t for t in backend.get_all_traces() if t["service_name"] == "multi-test"]
        assert len(traces) == 3

        # Each trace should have a unique ID
        trace_ids = {t["trace_id"] for t in traces}
        assert len(trace_ids) == 3
