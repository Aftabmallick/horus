# Module: `agent_tracer_plus.simulator.what_if`

What-if scenario engine for traces.

## Class `WhatIfEngine`
Engine for what-if scenarios (latency, cost, throughput).

Allows hypothetical analysis like:
  - "What if latency was 2x slower?"
  - "What if we added caching and reduced token usage by 40%?"
  - "What if error rate doubles?"

### `def __init__(self)`
