# Module: `agent_tracer_plus.storage.ndjson`

NDJSON (Newline Delimited JSON) file storage backend.

Append-only .jsonl files — crash-safe, human-readable, great for debugging.

## Class `NDJSONBackend`
Stores traces and spans as newline-delimited JSON files.

Args:
    directory: Directory to store .jsonl files. Created if it doesn't exist.

### `def __init__(self, directory)`
### `def _write_line(filepath, line)`
### `def _write_lines(filepath, lines)`
### `def _find_trace(self, trace_id)`
### `def _find_spans(self, trace_id)`
### `def _query(self, filters, limit, offset)`
