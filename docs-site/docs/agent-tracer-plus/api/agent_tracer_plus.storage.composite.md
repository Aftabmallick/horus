# Module: `agent_tracer_plus.storage.composite`

Composite storage backend (fan-out) with circuit breaker protection.

Allows writing traces to multiple storage backends simultaneously.
For example, writing to local SQLite for fast queries, and S3 for archiving.

If a secondary backend fails repeatedly, its circuit breaker opens and it is
temporarily skipped — protecting throughput and preventing cascading failures.

## Class `CompositeBackend`
Writes data to multiple backends simultaneously with circuit breaker protection.

Reads (queries, get) are served from the primary (first) backend.

Args:
    backends: List of storage backends. First is primary (reads + writes).
    failure_threshold: Failures before opening a secondary backend's circuit.
    recovery_timeout: Seconds before attempting recovery on an open circuit.

### `def __init__(self, backends, failure_threshold, recovery_timeout)`
