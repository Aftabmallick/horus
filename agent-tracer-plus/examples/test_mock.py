import asyncio
import logging

logging.basicConfig(level=logging.INFO)

import agent_tracer_plus
from agent_tracer_plus.core.context import get_tracer
from agent_tracer_plus.decorators.agent import trace_agent
from agent_tracer_plus.decorators.llm import trace_llm
from agent_tracer_plus.storage.http import HttpBackend

agent_tracer_plus.init(
    service_name="agno-test-agent",
    storage=HttpBackend(
        host="http://localhost:3000",
        public_key="pk_default",
        secret_key="sk_default"
    )
)

@trace_agent(name="ResearchAgent", tags=["framework:agno"])
def run_mock_agent(prompt: str) -> str:
    print(f"[*] Starting Agno Agent for prompt: {prompt}")

    @trace_llm(name="openai.gpt-4o-mini", model="gpt-4o-mini")
    def call_llm():
        return "SpaceX Starship is doing great!"

    return call_llm()

async def main():
    print("--- Agno Agent Tracer Demo (MOCKED) ---")
    result = run_mock_agent("What is the latest news regarding SpaceX Starship?")
    print("\n[Agent Output]")
    print(result)

    print("\n[*] Waiting for Kafka background worker to flush traces...")

    # tracer.shutdown() flushes the BatchProcessor queue to the HttpBackend,
    # and then calls HttpBackend.close() which drains its thread queue and sends via HTTP.
    await get_tracer().shutdown()

    print("[*] Traces flushed to http://localhost:3000 successfully!")

if __name__ == "__main__":
    asyncio.run(main())
