# Module: `agent_tracer_plus.alerts.channels`

Alerting channels.

## Class `AlertChannel`
Base class for alert delivery channels.

### `def send(self, subject, message)`
## Class `WebhookChannel`
Sends alerts to a generic webhook.

### `def __init__(self, url)`
### `def send(self, subject, message)`
## Class `SlackChannel`
Sends alerts to a Slack Incoming Webhook.

### `def __init__(self, webhook_url)`
### `def send(self, subject, message)`
