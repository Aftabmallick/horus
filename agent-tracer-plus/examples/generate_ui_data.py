"""Generate dummy trace data for the UI."""

import asyncio

import agent_tracer_plus
from agent_tracer_plus import init, trace_agent, trace_step


@trace_step(name="database_query")
async def db_query(sql: str):
    await asyncio.sleep(0.5)
    return [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]

@trace_step(name="llm_processing")
async def process_data(data: list):
    span = agent_tracer_plus.core.context.get_current_span()
    if span:
        span.token_usage = {"input_tokens": 120, "output_tokens": 40, "total_tokens": 160}
        span.cost_info = {"total_cost": 0.003, "model": "gpt-4"}
    await asyncio.sleep(1.0)
    return "Processed 2 records."

@trace_agent(name="DataAnalysisAgent")
async def run_agent(query: str):
    data = await db_query("SELECT * FROM users")
    result = await process_data(data)

    # Simulate a failing step
    with agent_tracer_plus.core.context.SpanContext("external_api_call"):
        await asyncio.sleep(0.2)
        # intentionally not failing here to mix up data

    return result

async def main():
    print("Generating traces...")
    init(service_name="dummy-service", storage="sqlite://dummy_traces.db")

    for i in range(5):
        await run_agent(f"query_{i}")

    print("Done generating traces. Run `agent-tracer-plus ui` to view.")

if __name__ == "__main__":
    asyncio.run(main())
