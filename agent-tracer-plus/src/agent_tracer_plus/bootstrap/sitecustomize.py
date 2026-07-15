"""Auto-injected sitecustomize module for Agent Tracer Plus.

This file is automatically added to PYTHONPATH by the `agent-tracer-plus run`
CLI command. When the target Python interpreter starts up, it automatically
imports `sitecustomize`, which then imports and initializes the tracer
before any user code runs.
"""

import os

if os.environ.get("AGENT_TRACER_PLUS_AUTO_INIT") == "1":
    try:
        import agent_tracer_plus
        agent_tracer_plus.init()
    except Exception as e:
        import sys
        print(f"Failed to auto-initialize Agent Tracer Plus: {e}", file=sys.stderr)
