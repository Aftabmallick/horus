# Module: `agent_tracer_plus.query.filters`

Trace query filters for Agent Tracer Plus.

## Class `TraceFilter`
Structured filter for querying traces.

### `def to_dict(self)`
Convert to a dict suitable for storage backends.

### `def apply_time_range(self)`
Parse time_range string and set since/until.

### `def matches(self, trace_dict)`
Check if a trace dict matches this filter (client-side filtering).

## Function `build_filter()`
Build a TraceFilter from keyword arguments.

