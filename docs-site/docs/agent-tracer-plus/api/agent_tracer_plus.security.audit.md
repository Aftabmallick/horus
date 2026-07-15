# Module: `agent_tracer_plus.security.audit`

Audit logging framework for Agent Tracer Plus.

## Class `AuditAction`
Types of actions that can be audited.

## Class `AuditLogger`
Enterprise audit logger for security events.

### `def __init__(self, backend_url)`
### `def log_event(self, action, actor, target, ip_address, metadata, success)`
Log a security or access event.

### `def _send_to_backend(self, event)`
Send the audit event to a remote backend (stub).

### `def log_access_denied(self, actor, target, reason)`
Helper to log access denied events.

### `def log_trace_view(self, actor, trace_id, ip_address)`
Helper to log when a user views a trace.

## Class `S3WormAuditSink`
WORM-compliant audit sink that pushes events to an S3 bucket with Object Lock enabled.

### `def __init__(self, bucket, prefix)`
### `def _init_s3(self)`
### `def send(self, event)`
