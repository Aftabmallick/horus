# Module: `agent_tracer_plus.processing.metrics`

Prometheus metrics for Agent Tracer Plus self-monitoring.

Exposes internal SDK health metrics so the tracer itself is observable.
These are opt-in and require `prometheus_client` to be installed.

Metrics exposed:
    - agent_tracer_spans_processed_total (Counter): Total spans processed
    - agent_tracer_traces_processed_total (Counter): Total traces processed
    - agent_tracer_queue_depth (Gauge): Current batch processor queue depth
    - agent_tracer_flush_latency_seconds (Histogram): Time to flush a batch
    - agent_tracer_drop_total (Counter): Spans dropped due to queue overflow
    - agent_tracer_backend_errors_total (Counter): Storage backend write errors
    - agent_tracer_batch_size (Histogram): Size of each flushed batch

Usage::

    from agent_tracer_plus.processing.metrics import TracerMetrics
    metrics = TracerMetrics()
    metrics.record_span_processed()
    metrics.record_flush(batch_size=50, latency_seconds=0.012)

## Function `_try_import_prometheus()`
## Class `TracerMetrics`
Prometheus metrics registry for SDK self-monitoring.

If `prometheus_client` is not installed, all methods are no-ops.

### `def __init__(self, namespace)`
### `def _init_metrics(self)`
Initialize all Prometheus metric objects.

### `def record_span_processed(self, status)`
Increment the spans processed counter.

### `def record_trace_flushed(self, status)`
Increment the traces flushed counter.

### `def set_queue_depth(self, depth)`
Update the queue depth gauge.

### `def record_flush(self, batch_size, latency_seconds)`
Record a completed flush operation.

### `def record_drop(self, reason)`
Increment the drop counter.

### `def record_backend_error(self, backend_name)`
Increment the backend error counter.

### `def timed_flush(self)`
Context manager that measures and records flush latency.

### `def is_available(self)`
Return True if prometheus_client is available and metrics are initialized.

