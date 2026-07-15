# Module: `agent_tracer_plus.storage.grpc_backend`

## Class `GrpcBackend`
### `def __init__(self, host, public_key, secret_key, max_queue_size)`
### `def _get_metadata(self)`
### `def _enqueue(self, item_type, item_data)`
### `def _worker_loop(self)`
### `def _send_trace(self, trace_data)`
### `def _send_span(self, span_data)`
### `def _sync_flush(self)`
