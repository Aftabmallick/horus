# Module: `agent_tracer_plus.core.config`

Configuration management for Agent Tracer Plus.

## Class `TracerConfig`
Configuration for the AgentTracerPlus tracer.

All fields have sensible defaults — the tracer works with zero config.

### `def from_dict(cls, data)`
Create config from a dictionary, ignoring unknown keys.

### `def from_env(cls)`
Create config from environment variables.

