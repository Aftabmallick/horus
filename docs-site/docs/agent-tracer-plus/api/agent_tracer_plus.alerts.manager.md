# Module: `agent_tracer_plus.alerts.manager`

Smart Alerting Manager for Agent Tracer Plus.

## Class `AlertCondition`
### `def __init__(self, key, operator, value)`
### `def evaluate(self, trace_data)`
## Class `AlertDestination`
Base class for alert destinations.

## Class `SlackDestination`
### `def __init__(self, webhook_url)`
## Class `PagerDutyDestination`
Triggers an incident in PagerDuty via the Events API v2.

### `def __init__(self, routing_key)`
## Class `WebhookDestination`
### `def __init__(self, url)`
## Class `AlertManager`
Evaluates traces against rules and dispatches alerts with debouncing.

### `def __init__(self, rules)`
