# Module: `agent_tracer_plus.security.masking`

PII Masking module for Agent Tracer Plus.

## Class `PIIMasker`
Masks Personally Identifiable Information in traces and spans.

### `def __init__(self, custom_patterns)`
### `def scrub_text(self, text)`
Apply all regex patterns to replace sensitive data with [REDACTED].

### `def scrub_data(self, data)`
Recursively scrub data structures (dicts, lists, strings).

### `def mask_span(self, span)`
Scrub inputs, outputs, and attributes of a span in-place.

### `def mask_trace(self, trace)`
Scrub trace metadata and all attached spans in-place.

