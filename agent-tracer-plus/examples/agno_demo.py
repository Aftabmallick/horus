"""
Demo showing how to use Agent Tracer Plus with Agno (formerly Phidata).

Before running:
1. Ensure the platform cluster is running (`cd ../agent-tracer-platform && docker-compose up -d`)
2. Install agno: `pip install agno openai`
3. Set your OpenAI key: `export OPENAI_API_KEY=sk-...`
"""

import asyncio
import os

from agent_tracer_plus.core.decorators import trace_agent, trace_llm, trace_tool
from agno.agent import Agent, RunResponse
from agno.models.openai import OpenAIChat
from agno.tools.duckduckgo import DuckDuckGoTools

import agent_tracer_plus

# Initialize the Tracer to point to your new Kafka/ClickHouse platform
agent_tracer_plus.init(
    service_name="agno-test-agent",
    storage_backend="http",
    host="http://localhost:3000",
    public_key="pk_default",
    secret_key="sk_default"
)

# ------------------------------------------------------------------------
# Step 1: Instrument Agno's components
# We manually decorate the tool and model execution to trace everything.
# ------------------------------------------------------------------------

# 1. Trace a custom tool
@trace_tool(name="web_search")
def run_search(query: str):
    print(f"[*] Executing Web Search: {query}")
    # We could use Agno's built-in tool, but here's a wrapped custom one
    ddg = DuckDuckGoTools()
    return ddg.search(query)

# 2. Trace the Agent's Run
@trace_agent(name="ResearchAgent", metadata={"framework": "agno"})
def run_agno_agent(prompt: str) -> str:
    print(f"[*] Starting Agno Agent for prompt: {prompt}")

    agent = Agent(
        model=OpenAIChat(id="gpt-4o-mini"),
        tools=[run_search],
        description="You are a brilliant researcher.",
        show_tool_calls=True,
    )

    # We use a nested trace_llm context for the actual LLM call
    @trace_llm(name="openai.gpt-4o-mini", model_name="gpt-4o-mini")
    def call_llm():
        response: RunResponse = agent.run(prompt)
        return response.content

    return call_llm()

# ------------------------------------------------------------------------
# Step 2: Run the test
# ------------------------------------------------------------------------

async def main():
    if not os.getenv("OPENAI_API_KEY"):
        print("Please set OPENAI_API_KEY to run the Agno model.")
        return

    print("--- Agno Agent Tracer Demo ---")

    # Execute the agent
    result = run_agno_agent("What is the latest news regarding SpaceX Starship?")
    print("\n[Agent Output]")
    print(result)

    print("\n[*] Waiting for Kafka background worker to flush traces...")
    # The HTTP backend uses a background thread and queue, so it doesn't block.
    # We await flush() to ensure it transmits before script exit.
    await agent_tracer_plus.get_tracer().storage.flush()
    print("[*] Traces flushed to http://localhost:3000 successfully!")
    print("[*] You can view them in ClickHouse via the Platform UI.")

if __name__ == "__main__":
    asyncio.run(main())
