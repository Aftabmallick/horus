# Module: `agent_tracer_plus.storage.s3`

S3 Archival Storage Backend.

## Class `S3Backend`
Archival storage backend using S3 for traces.

Traces and spans are saved as NDJSON objects in S3 buckets.

### `def __init__(self, bucket, prefix)`
### `def _generate_key(self, trace_id, obj_type)`
