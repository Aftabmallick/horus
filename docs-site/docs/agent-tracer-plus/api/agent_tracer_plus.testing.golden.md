# Module: `agent_tracer_plus.testing.golden`

Golden trace baseline management.

## Class `GoldenTrace`
Represents a frozen 'golden' trace used as a testing baseline.

### `def __init__(self, trace, spans, name)`
### `def save(self, directory)`
Save the golden trace to disk.

### `def load(cls, file_path)`
Load a golden trace from disk.

### `def assert_matches(self, actual_spans, strict)`
Assert that an actual trace execution matches this golden baseline.

Args:
    actual_spans: The spans produced by the replay/test execution.
    strict: If True, requires exact output matching. If False, just checks structure.

