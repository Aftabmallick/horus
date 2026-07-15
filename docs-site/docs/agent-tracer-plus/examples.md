---
sidebar_position: 5
---

# 🚀 The "Everything-Included" Mega Example

This page demonstrates a production-ready, hyper-scale application using **Agent Tracer Plus**. It incorporates nearly every advanced module in the SDK, including Chaos Engineering, PII Redaction, Budgeting, Shadow Experiments, SLAs, and Multimodal tracking.

## The Scenario: High-Security Medical Triage

Imagine an AI application that receives medical inquiries containing sensitive patient data, images, and text. We need to:
1. Ensure the patient's SSN or names are redacted before hitting the tracing database.
2. Ensure the agent never costs more than $0.05 per run.
3. Automatically shadow-test a new Claude 3 prompt against our production GPT-4 prompt.
4. Occasionally inject chaos faults to ensure our error-handling is resilient.

### Complete Annotated Script

```python
import asyncio
from agent_tracer_plus.core.tracer import AgentTracer
from agent_tracer_plus.storage.clickhouse import ClickHouseStorage
from agent_tracer_plus.decorators.tracing import trace_agent, trace_llm

# Advanced Modules
from agent_tracer_plus.security.redaction import Redactor
from agent_tracer_plus.budget.manager import BudgetManager
from agent_tracer_plus.experiments.shadow import ShadowExperiment
from agent_tracer_plus.chaos.injector import ChaosInjector
from agent_tracer_plus.sla.monitor import SLAMonitor
from agent_tracer_plus.multimodal.tracker import MultimodalTracker
from agent_tracer_plus.auto.openai import patch_openai

# 1. Initialize Auto-Instrumentation
# This automatically captures all native OpenAI API calls in your script!
patch_openai()

# 2. Setup the Enterprise Storage Backend
storage = ClickHouseStorage(host="clickhouse-prod.internal")

# 3. Configure Security and Rules
# Scrub Social Security Numbers and Emails from traces before they are saved
redactor = Redactor(patterns=[r"\d{3}-\d{2}-\d{4}", r"[\w\.-]+@[\w\.-]+"])

# Hard stop the agent if it exceeds $0.05 per trace
budget = BudgetManager(max_cost=0.05)

# 4. Initialize the Global Tracer with Middlewares
tracer = AgentTracer(
    storage_backend=storage, 
    tenant_id="med_health_inc",
    middlewares=[redactor, budget]
)

# 5. Configure Reliability & Testing
# Alert if the triage process takes longer than 3 seconds
sla_monitor = SLAMonitor(max_latency_ms=3000)

# Simulate network drops on 1% of LLM calls in staging
chaos = ChaosInjector(failure_rate=0.01)

# Route 10% of traffic to a shadow prompt without affecting the user
shadow_test = ShadowExperiment(
    experiment_name="claude_triage_v2", 
    routing_percentage=0.1
)

# ---------------------------------------------------------
# Application Logic
# ---------------------------------------------------------

@trace_llm(name="GPT-4-Vision-Triage")
async def analyze_symptoms(text: str, image_bytes: bytes) -> str:
    """Analyzes text and medical images to output a triage priority."""
    # Inject Chaos (simulates exceptions 1% of the time)
    chaos.maybe_fail()
    
    # Track Multimodal bandwidth
    tracker = MultimodalTracker()
    tracker.record_image_input(image_bytes)
    
    # Shadow Test: Send the same inputs to Claude in the background
    await shadow_test.run_shadow(
        func=experimental_claude_triage, 
        kwargs={"text": text}
    )
    
    # Simulate the actual LLM call...
    await asyncio.sleep(1.5)
    
    # The budget manager will automatically calculate token costs here
    # based on the returned payload size!
    return "Priority: HIGH (Requires immediate attention)"


async def experimental_claude_triage(text: str) -> str:
    """This function is executed in the background by the ShadowExperiment."""
    await asyncio.sleep(1.0)
    return "Priority: URGENT"


@trace_agent(name="MedicalTriageAgent")
async def run_medical_triage(patient_data: str, scan_image: bytes) -> str:
    """
    Main Orchestrator Agent. 
    The trace context is automatically propagated down to `analyze_symptoms`.
    """
    with sla_monitor.watch(context="full_triage_cycle"):
        # The Redactor will ensure "John Doe" is scrubbed from the final trace!
        result = await analyze_symptoms(text=patient_data, image_bytes=scan_image)
        return result

# ---------------------------------------------------------
# Execution
# ---------------------------------------------------------

async def main():
    print("Starting Medical Triage Pipeline...")
    
    sensitive_input = "Patient John Doe (Email: john@doe.com) reports chest pain."
    dummy_xray = b"\x00\x01\x02" # Dummy image bytes
    
    try:
        response = await run_medical_triage(sensitive_input, dummy_xray)
        print(f"Agent Output: {response}")
    except Exception as e:
        print(f"Pipeline failed (potentially due to Chaos Injector or Budget Manager): {e}")
        
    # Flush all traces to ClickHouse
    await tracer.flush()

if __name__ == "__main__":
    asyncio.run(main())
```

### What's happening under the hood?

When you run this script:
1. **Context Propagation**: The `@trace_agent` decorator creates a Root Trace. As `analyze_symptoms` is called, the trace ID is seamlessly passed via `contextvars`, making it a Child Span.
2. **Security**: The `Redactor` middleware intercepts the trace before it hits ClickHouse and scrubs `john@doe.com`.
3. **Asynchronous Execution**: The `ShadowExperiment` fires off the experimental Claude function in the background, allowing the user's GPT-4 response to return instantly.
4. **Performance Validation**: If `analyze_symptoms` and the main agent take longer than 3 seconds combined, the `SLAMonitor` dispatches an alert payload to your configured Webhook.
