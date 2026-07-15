# Module: `agent_tracer_plus.processing.sampling`

Sampling engine for traces.

## Class `Sampler`
Determines whether a trace should be captured or dropped.

### `def __init__(self, rate, conditional)`
Args:
    rate: The base head-based sampling rate (0.0 to 1.0).
    conditional: A function that takes a trace and returns True to ALWAYS sample it
                 (e.g., always sample errors).

### `def should_sample(self, trace)`
Evaluate if the trace should be sampled.

