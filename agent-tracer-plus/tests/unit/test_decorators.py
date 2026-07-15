import pytest

from agent_tracer_plus import current_span, trace_agent, trace_step
from agent_tracer_plus.core.context import get_current_trace


@trace_agent(name="FuncAgent")
def sync_agent(x: int):
    step1(x)
    return x * 2

@trace_step(name="step1")
def step1(x: int):
    span = current_span()
    assert span is not None
    span.set_attribute("x", x)

def test_sync_function_decorators():
    result = sync_agent(5)
    assert result == 10
    # The trace is finished and popped from context, but we can verify it executed cleanly
    assert get_current_trace() is None

@pytest.mark.asyncio
async def test_async_class_decorators():
    @trace_agent(name="ClassAgent")
    class MyAgent:
        async def run(self):
            return await self.helper()

        async def helper(self):
            return "done"

    agent = MyAgent()
    assert await agent.run() == "done"
