# Module: `agent_tracer_plus.budget.tracker`

Token usage tracker for Agent Tracer Plus.

## Class `UsageTracker`
Tracks token and cost usage across traces.

### `def __init__(self, enforcer)`
### `def record_usage(self, trace_id, tenant_id, agent_name, tokens, cost)`
Record usage and enforce budgets.

### `def get_tenant_usage(self, tenant_id)`
Get current usage for a tenant.

### `def get_agent_usage(self, agent_name)`
Get current usage for an agent.

### `def reset(self)`
Reset all usage metrics.

