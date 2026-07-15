# Module: `agent_tracer_plus.core.tracer`

AgentTracerPlus — the main tracer engine.

This is the central class that orchestrates auto-instrumentation,
storage, batch processing, and context management.

## Class `AgentTracerPlus`
The main tracer engine.

Usage:
    tracer = AgentTracerPlus(service_name="my-app")
    tracer.start()
    # ... your code ...
    await tracer.shutdown()

Or via the global init():
    import agent_tracer_plus
    agent_tracer_plus.init(service_name="my-app")

### `def __init__(self, config)`
### `def _init_storage(self, storage)`
Initialize storage backend from config value.

### `def _storage_from_uri(uri)`
Create a storage backend from a URI string.

### `def start(self)`
Start the tracer — begin auto-instrumentation and batch processing.

### `def _apply_auto_patches(self)`
Apply monkey patches for auto-instrumentation.

### `def _enqueue_trace(self, trace)`
Enqueue a completed trace for storage.

### `def _enqueue_span(self, span)`
Enqueue a completed span for storage.

### `def check_replay(self, span_type, name, input_payload)`
Check if execution should be mocked by the ReplayEngine.

### `def storage(self)`
Access the storage backend directly.

