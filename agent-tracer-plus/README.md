# Horus: Agent Tracer Plus 🚀

> Production-grade auto-capture tracing for AI agents. Zero code changes required.

[![PyPI version](https://badge.fury.io/py/agent-tracer-plus.svg)](https://pypi.org/project/agent-tracer-plus/)
[![Python versions](https://img.shields.io/pypi/pyversions/agent-tracer-plus)](https://pypi.org/project/agent-tracer-plus/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Agent Tracer Plus gives you ultimate visibility into your autonomous agents, RAG pipelines, and LLM calls. It auto-instruments your existing code to capture inputs, outputs, tokens, costs, and tool calls — then provides an intelligence layer to analyze them.

---

## ⚡ Zero Code Integration

You don't need to rewrite your application. Just run it through our CLI:

```bash
pip install agent-tracer-plus

# Run your existing script — it's instantly traced!
agent-tracer-plus run python my_agent.py
```

Or add **one line of code** to the top of your app:

```python
import agent_tracer_plus
agent_tracer_plus.init(service_name="my-recruiter-agent")

import openai
# The tracer automatically patches OpenAI, Anthropic, HTTPX, and MCP tools
response = openai.chat.completions.create(model="gpt-4o", messages=[...])
```

---

## 🌟 Feature Matrix

| Category | Feature | Status |
|:---|:---|:---:|
| **Tracing** | OpenAI & Anthropic auto-capture (inc. streaming) | ✅ |
| | HTTP (requests/httpx) & DB (sqlalchemy) | ✅ |
| | MCP Protocol Client/Server tools | ✅ |
| **Storage** | SQLite, PostgreSQL, ClickHouse, MongoDB | ✅ |
| | OpenTelemetry (OTLP) Native Exporter | ✅ |
| **Control** | Hard Token & Cost Budgets (Real-time kills) | ✅ |
| | PII Data Redaction (Regex + Presidio) | ✅ |
| **Intelligence**| Hallucination Detection (Cross-Encoder) | ✅ |
| | Online Anomaly Detection (EWMA loops/latency) | ✅ |
| | Time-Travel Replay (Deterministic mock execution)| ✅ |
| **Ops** | Live Tail WebSocket streaming (w/ filters) | ✅ |
| | A/B Experiment Analysis from storage | ✅ |

---

## 🛠️ The 3 Ways to Instrument

### 1. Auto-Instrumentation (Zero-Code)
The `agent-tracer-plus run` command uses Python's `sitecustomize` mechanism to inject the tracer before your code even boots.

### 2. Manual Decorators (Fine-Grained)
```python
from agent_tracer_plus import trace_agent, trace_step, trace_tool

@trace_agent(name="DataScientistAgent")
class Agent:
    @trace_tool(name="execute_sql")
    async def query_db(self, query: str):
        ...
```

### 3. Context Managers (Block-level)
```python
from agent_tracer_plus import trace_block

with trace_block("complex_reasoning_step", capture_input=True) as span:
    span.set_attribute("context_size", 1024)
    # do work
```

---

## 🛡️ Real-time Budgets (Guardrails)

Don't wake up to a $5,000 OpenAI bill because your agent got stuck in a loop.

```python
import agent_tracer_plus
from agent_tracer_plus.budget.enforcer import TokenBudget

agent_tracer_plus.init(
    budget=TokenBudget(
        max_cost_per_minute=2.00,  # $2/min sliding window
        max_cost_per_trace=5.00,   # $5 max per agent execution
        on_exceed="kill"           # Hard-kills the asyncio task if exceeded
    )
)
```

---

## 📡 Live Tail & OpenTelemetry

Want to watch your agents think in real-time?
```bash
agent_tracer_plus.init(live_tail=True)
# Connect via WebSockets: ws://localhost:8765/?filter=status:error
```

Want to send traces to Datadog, Jaeger, or Grafana?
```python
agent_tracer_plus.init(storage="otlp://localhost:4317")
```

---

## 📚 Documentation

Full documentation is available at [docs.agent-tracer-plus.io](https://docs.agent-tracer-plus.io), including guides on:
- Configuring the 13 storage backends
- Setting up Chaos Engineering (fault injection)
- Writing custom Plugins

## License
MIT License. See [LICENSE](LICENSE) for details.
