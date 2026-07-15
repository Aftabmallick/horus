# Module: `agent_tracer_plus.testing.evaluators`

Evaluation functions and protocols for scoring traces.

## Class `Score`
Represents a score from an evaluator.

## Class `Evaluator`
Protocol for all evaluators.

## Class `ExactMatchEvaluator`
Evaluates if the actual string exactly matches the expected string.

### `def __init__(self, name)`
## Class `ContainsEvaluator`
Evaluates if the actual string contains the expected substring.

### `def __init__(self, name)`
## Class `RegexEvaluator`
Evaluates if the actual string matches a specific regex pattern (expected is ignored or used as pattern).

### `def __init__(self, pattern, name)`
## Class `JSONSchemaEvaluator`
Evaluates if the actual output is valid JSON (and optionally matches a schema).

### `def __init__(self, name)`
