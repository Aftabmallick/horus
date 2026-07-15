# Module: `agent_tracer_plus.chaos.faults`

Fault injection types.

## Class `Fault`
Base class for chaos engineering faults.

### `def __init__(self, target, probability)`
## Class `LatencyFault`
### `def __init__(self, target, delay_ms, probability)`
## Class `ErrorFault`
### `def __init__(self, target, exception, probability)`
## Class `EmptyResponseFault`
### `def __init__(self, target, probability)`
