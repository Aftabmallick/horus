# Module: `agent_tracer_plus.bootstrap.sitecustomize`

Auto-injected sitecustomize module for Agent Tracer Plus.

This file is automatically added to PYTHONPATH by the `agent-tracer-plus run`
CLI command. When the target Python interpreter starts up, it automatically
imports `sitecustomize`, which then imports and initializes the tracer
before any user code runs.

