# Module: `agent_tracer_plus.sla.reporter`

SLA compliance reporting.

## Class `SLAReporter`
Generate SLA compliance reports from trace data.

### `def __init__(self, slas)`
### `def _calculate_metric(self, metric, stats)`
Calculate the actual value for a metric.

### `def _check_compliance(self, metric, actual, threshold)`
Check if a metric value meets the SLA threshold.

