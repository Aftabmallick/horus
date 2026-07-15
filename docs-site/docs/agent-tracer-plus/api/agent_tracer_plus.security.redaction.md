# Module: `agent_tracer_plus.security.redaction`

PII redaction using regex patterns.

## Class `PIIRedactor`
Scrub sensitive information from payloads before storage.

### `def __init__(self, patterns)`
### `def redact_text(self, text)`
Apply all regex patterns to replace matches with [REDACTED:&lt;type&gt;].

### `def redact_payload(self, payload)`
Recursively scrub strings within a dictionary or list.

