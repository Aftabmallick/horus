"""Examples of using Agent Tracer Plus manual decorators."""

import asyncio

from agent_tracer_plus import init, trace_agent, trace_step, trace_tool

# 1. Initialize tracer (creates SQLite db by default)
init(service_name="demo-app")

@trace_tool(name="search_db")
def search_db(query: str) -> str:
    print(f"Searching for: {query}")
    return "Result: 42"

@trace_step(name="process_data")
async def process_data(data: str) -> str:
    print(f"Processing: {data}")
    await asyncio.sleep(0.1)
    return f"Processed {data}"

@trace_agent(name="MyAwesomeAgent")
async def my_agent(user_query: str) -> str:
    print(f"Agent starting for: {user_query}")

    # 1. Call a traced tool
    raw_data = search_db(user_query)

    # 2. Call a traced step
    result = await process_data(raw_data)

    return result

if __name__ == "__main__":
    asyncio.run(my_agent("What is the meaning of life?"))
    print("Done! Check agent_traces.db for the trace.")
