# Module: `agent_tracer_plus.storage.memory`

In-memory storage backend for testing and development.

## Class `InMemoryBackend`
Stores traces and spans in memory. Data is lost on restart.

Thread-safe via a lock. Ideal for unit tests and short-lived scripts.

### `def __init__(self, max_traces)`
### `def trace_count(self)`
Number of stored traces.

### `def span_count(self)`
Total number of stored spans across all traces.

### `def get_all_traces(self)`
Get all stored trace dicts.

### `def get_all_spans(self)`
Get all stored span dicts.

