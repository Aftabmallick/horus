# Module: `agent_tracer_plus.intelligence.diagnosis`

AI Root Cause Analysis for traces.

## Class `TraceDiagnoser`
Uses an LLM to diagnose failures within a trace tree.

### `def __init__(self, api_key, model)`
### `def _format_trace_for_llm(self, trace, spans)`
Compress the trace into a readable format for the LLM using DAG topology.

