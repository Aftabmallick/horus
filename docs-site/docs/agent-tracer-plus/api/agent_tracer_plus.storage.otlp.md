# Module: `agent_tracer_plus.storage.otlp`

OpenTelemetry (OTLP) storage backend.

## Class `OTLPBackend`
Storage backend that forwards traces and spans to an OTLP endpoint (e.g., Datadog, Honeycomb, New Relic).

### `def __init__(self, endpoint, service_name)`
### `def _convert_timestamp(self, ts_str)`
