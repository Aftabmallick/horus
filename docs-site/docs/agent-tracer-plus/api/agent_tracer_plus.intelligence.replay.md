# Module: `agent_tracer_plus.intelligence.replay`

Time-Travel Replay Engine for Agent Tracer Plus.

## Class `ReplayError`
Exception raised during replay when execution diverges unexpectedly.

## Class `ReplayEngine`
Replays a historical trace deterministically.

This engine integrates with the core tracer. When an auto-instrumented
function is called (LLM, HTTP, Tool), the tracer asks the ReplayEngine
if it should be mocked. The engine matches the call against historical
spans by type, name, and input hash.

### `def __init__(self, trace_id, storage, diverge_span_id)`
### `def _hash_payload(self, payload)`
Create a deterministic hash of an input payload.

### `def _parse_output(self, output)`
Attempt to parse stored JSON output back into objects.

### `def should_mock(self, span_type, name, input_payload)`
Check if the current execution should be short-circuited and mocked.

Returns:
    (should_mock: bool, mock_output: Any)

