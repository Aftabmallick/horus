# Module: `agent_tracer_plus.core.versioning`

Prompt Versioning Manager for Agent Tracer Plus.

## Class `PromptVersionTracker`
Tracks prompt templates by hashing them to auto-detect versions.

### `def get_version(cls, template)`
Hash a template string to get its version ID (e.g. v_a1b2c3d4).

## Function `track_prompt(template, span)`
Helper to track prompt and attach version to a span.

