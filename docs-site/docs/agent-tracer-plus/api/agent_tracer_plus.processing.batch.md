# Module: `agent_tracer_plus.processing.batch`

Async batch processor for buffered writes to storage backends.

Collects spans/traces in an in-memory queue and flushes them
to the storage backend in batches — reducing I/O overhead.

## Class `CircuitBreaker`
Simple state-based circuit breaker to prevent cascading failures.

### `def __init__(self, failure_threshold, reset_timeout)`
### `def record_success(self)`
### `def record_failure(self)`
### `def can_execute(self)`
## Class `BatchProcessor`
Buffers trace/span data and flushes to storage in batches.

Runs a background flush loop. Thread-safe.

### `def __init__(self, storage, batch_size, flush_interval, max_queue_size)`
### `def start(self, loop)`
Start the background flush loop.

### `def enqueue_trace(self, trace)`
Add a trace to the flush queue.

### `def enqueue_span(self, span)`
Add a span to the flush queue.

### `def _should_flush(self)`
Check if we should trigger a flush based on queue size.

### `def _try_flush(self)`
Try to trigger an async flush.

### `def _sync_flush_on_exit(self)`
Synchronous flush for atexit handler.

### `def pending_count(self)`
Number of items waiting to be flushed.

