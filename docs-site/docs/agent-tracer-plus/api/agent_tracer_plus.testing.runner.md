# Module: `agent_tracer_plus.testing.runner`

Concurrent evaluation runner for prompt testing suites.

## Class `EvalResult`
The result of evaluating a single test case.

## Class `SuiteResult`
The aggregated result of evaluating an entire suite.

### `def average_score(self, evaluator_name)`
Calculate the average score for a specific evaluator.

## Class `AsyncEvalRunner`
Runs evaluation suites concurrently.

### `def __init__(self, concurrency)`
