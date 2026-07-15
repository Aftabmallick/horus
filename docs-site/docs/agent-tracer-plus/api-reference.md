---
sidebar_position: 3
---

# API Reference

## The AgentTracer Class
The `AgentTracer` is the core entry point for capturing and exporting telemetry.

```python
from agent_tracer_plus.core.tracer import AgentTracer

tracer = AgentTracer(
    storage_backend=backend,
    tenant_id="customer_xyz",
    service_name="payment_agent"
)
```

## Decorators
Agent Tracer Plus provides powerful decorators to instantly instrument your functions.

### `@trace_agent`
Use this for high-level agent boundaries.

```python
@trace_agent(name="FinancialAdvisor")
def analyze_portfolio():
    pass
```

### `@trace_llm`
Use this for specific model calls. It natively parses token usage from standard LLM responses.

```python
@trace_llm(name="GPT-4")
async def get_chat_response():
    pass
```
