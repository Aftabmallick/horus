# Module: `agent_tracer_plus.decorators.guardrails`

Guardrail Monitoring Decorator for Agent Tracer Plus.

## Class `GuardrailResult`
Standard return type for guardrail functions.

### `def __init__(self, passed, reason, metadata)`
### `def __bool__(self)`
## Function `trace_guardrail(name, policy)`
Decorator to trace guardrail validation layers.

If the function returns a GuardrailResult or a bool, it will automatically
log if the guardrail passed or failed.

