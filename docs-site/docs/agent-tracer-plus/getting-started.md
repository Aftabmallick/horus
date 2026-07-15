---
sidebar_position: 1
---

# Getting Started

Agent Tracer Plus is an OpenTelemetry-native, high-performance tracing SDK for LangChain, LlamaIndex, and custom multi-agent architectures.

## Installation

Install the base package:
```bash
pip install agent-tracer-plus
```

### Storage Backends
If you plan to use an advanced storage backend, install the relevant dependencies:
```bash
pip install agent-tracer-plus[clickhouse]  # For ClickHouse
pip install agent-tracer-plus[redis]       # For Redis Streams
pip install agent-tracer-plus[kafka]       # For Kafka
pip install agent-tracer-plus[mongo]       # For MongoDB
```

## Quick Start

Initialize the tracer globally at the entry point of your application:

```python
from agent_tracer_plus.core.tracer import AgentTracer
from agent_tracer_plus.storage.sqlite import SQLiteBackend

# Initialize storage and tracer
storage = SQLiteBackend("sqlite:///agent_traces.db")
tracer = AgentTracer(storage_backend=storage, tenant_id="my_tenant")

# Use decorators to trace functions
from agent_tracer_plus.decorators.tracing import trace_agent, trace_llm

@trace_agent(name="CustomerSupportAgent")
def handle_query(query: str) -> str:
    return call_llm(query)

@trace_llm(name="GPT-4-Turbo")
def call_llm(prompt: str) -> str:
    # Your LLM call here
    return "Response from LLM"

# Run it!
handle_query("How do I reset my password?")
```

## Supported LLMs & Auto-Instrumentation
Agent Tracer Plus natively intercepts standard SDK calls to automatically capture token counts, costs, and latencies without manual decorators.

```python
from agent_tracer_plus.auto.openai import patch_openai

patch_openai() # Hooks into `openai.ChatCompletion.create`
```
