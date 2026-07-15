# Module: `agent_tracer_plus.decorators.agent`

@trace_agent decorator — marks the top-level agent execution.

## Function `trace_agent(func)`
## Function `trace_agent()`
## Function `trace_agent(func)`
Decorator to trace an agent function or class.

Creates a new Trace + root Span when the decorated function/method is called.

Can be used as:
    @trace_agent
    def my_agent(): ...

    @trace_agent(name="MyAgent")
    class MyAgent: ...

