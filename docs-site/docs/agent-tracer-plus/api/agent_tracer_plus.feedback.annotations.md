# Module: `agent_tracer_plus.feedback.annotations`

Team annotations and collaboration on traces.

## Class `Annotation`
A single annotation on a trace.

### `def to_dict(self)`
## Class `AnnotationStore`
In-memory annotation storage with query support.

### `def __init__(self)`
### `def add(self, trace_id, author, comment, tags, status)`
Add an annotation to a trace.

### `def get_for_trace(self, trace_id)`
Get all annotations for a trace.

### `def query(self, tags, status, author)`
Query annotations across all traces.

### `def update_status(self, annotation_id, new_status)`
Update the status of an annotation.

### `def delete(self, annotation_id)`
Delete an annotation.

### `def count(self)`
