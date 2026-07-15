# Module: `agent_tracer_plus.testing.suite`

Trace test suite management.

## Class `TraceTestSuite`
A collection of golden traces that serve as a regression suite.

### `def __init__(self, directory)`
### `def _load_all(self)`
Load all golden traces from the directory.

### `def from_production(cls, storage_backend, filter_args, sample_size)`
Draft method for pulling traces from production into a local suite.

