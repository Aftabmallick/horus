# Module: `agent_tracer_plus.testing.dataset`

Dataset and Suite abstractions for prompt testing.

## Class `EvalTestCase`
A single test case in an evaluation suite.

## Class `EvalSuite`
A collection of test cases and evaluators.

### `def __init__(self, name, evaluators)`
### `def add_case(self, name, input_data, expected_output, metadata)`
Add a test case to the suite.

### `def from_jsonl(cls, name, file_path, evaluators)`
Load an evaluation suite from a JSONL file.

