# Module: `agent_tracer_plus.alerts.rules`

Alerting rules engine.

## Class `AlertRule`
A rule that triggers an alert based on trace statistics.

### `def __init__(self, condition, channels, message_template, cooldown_seconds)`
### `def evaluate(self, stats)`
## Class `AlertEngine`
Evaluates rules against incoming trace data.

### `def __init__(self)`
### `def add_rule(self, rule)`
### `def evaluate(self, stats)`
Evaluate all rules against the provided stats (e.g. error_rate, latency).

