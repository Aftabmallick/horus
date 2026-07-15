# Module: `agent_tracer_plus.sla.monitor`

SLA Monitoring.

## Class `SLAMonitor`
Monitors trace metrics against SLA definitions using sliding windows and error budgets.

### `def __init__(self, window_size)`
### `def add_sla(self, agent, metric, threshold, error_budget)`
### `def _calculate_percentile(self, values, percentile)`
