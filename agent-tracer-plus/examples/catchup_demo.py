"""Demonstration of the Catch-Up Phase Killer Features."""

import asyncio
import logging

import agent_tracer_plus
from agent_tracer_plus import init, trace_agent, trace_llm
from agent_tracer_plus.alerts.manager import AlertCondition, WebhookDestination
from agent_tracer_plus.core.versioning import track_prompt
from agent_tracer_plus.decorators.guardrails import GuardrailResult, trace_guardrail
from agent_tracer_plus.graph.builder import build_dependency_graph

# 1. Init with Smart Alerting
init(
    service_name="catchup_demo",
    alerts=[
        {
            "name": "High Cost Alert",
            "condition": AlertCondition("total_cost", ">", 0.05),
            "destinations": [WebhookDestination("http://localhost:9999/mock-webhook")]
        }
    ]
)

# 2. Guardrail Decorator
@trace_guardrail(name="PII_Checker", policy="strict_no_emails")
def check_for_pii(text: str) -> GuardrailResult:
    """Blocks requests if they contain emails."""
    if "@" in text:
        return GuardrailResult(False, "Found email address in text", {"email": text})
    return GuardrailResult(True)


@trace_llm(model="gpt-4o")
async def call_llm(prompt_template: str, user_input: str):
    span = agent_tracer_plus.core.context.get_current_span()

    # 3. Prompt Versioning
    version = track_prompt(prompt_template, span)
    print(f"Tracking Prompt Version: {version}")

    # Simulate LLM call
    await asyncio.sleep(0.5)

    # Simulate high cost to trigger the alert
    span.cost_info = {"total_cost": 0.12, "model": "gpt-4o"}
    span.token_usage = {"total_tokens": 1000}

    return f"Processed: {user_input}"


@trace_agent(name="DataProcessorAgent")
async def main_agent(data: str):
    print("Running agent...")

    # Check guardrail
    if not check_for_pii(data):
        print("Guardrail blocked the request!")
        return "Blocked"

    template = "You are a helpful assistant. Process this: {}"
    return await call_llm(template, data)

async def main():
    # Run the agent
    await main_agent("Safe data")
    await main_agent("bad@email.com")

    # Flush tracer (which triggers the async alert evaluation)
    await agent_tracer_plus.core.context.get_tracer().flush()
    await asyncio.sleep(0.1)  # allow alert tasks to fire

    # 4. Auto Dependency Graph
    print("\n--- Auto Dependency Graph (Mermaid) ---")
    graph = await build_dependency_graph(limit=10)
    print(graph.to_mermaid())

    print("\n(To test Live Tail, run `agent-tracer-plus tail` in another terminal)")

if __name__ == "__main__":
    logging.basicConfig(level=logging.ERROR)
    asyncio.run(main())
