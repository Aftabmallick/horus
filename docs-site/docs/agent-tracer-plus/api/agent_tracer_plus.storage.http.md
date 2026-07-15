# Module: `agent_tracer_plus.storage.http`

Production HTTP Storage Backend for Agent Tracer Plus SaaS.

Uses a dedicated background thread and queue to ensure zero-overhead 
and resilience for the host application.

## Class `HttpBackend`
Sends traces over HTTP using a background worker thread.

### `def __init__(self, host, public_key, secret_key, max_queue_size)`
### `def _enqueue(self, item_type, item_data)`
Non-blocking enqueue. Drops data if the queue is full (circuit breaker).

### `def _worker_loop(self)`
Dedicated background thread for batching and sending data.

### `def _send_with_retry(self, endpoint, payload)`
### `def _sync_flush(self)`
Wait for the queue to empty before shutting down.

