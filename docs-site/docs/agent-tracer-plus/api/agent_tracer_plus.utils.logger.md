# Module: `agent_tracer_plus.utils.logger`

Internal logging for Agent Tracer Plus.

Uses a namespaced logger so users can control our log output
without interfering with their application logging.
Tracing errors are NEVER propagated to the user's application.

## Function `get_logger(name)`
Get a namespaced logger for internal use.

Args:
    name: Optional sub-name (e.g., "storage.sqlite").
          Will be prefixed with "agent_tracer_plus.".

Returns:
    A configured Logger instance.

