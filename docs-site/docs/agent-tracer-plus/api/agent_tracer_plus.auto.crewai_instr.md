# Module: `agent_tracer_plus.auto.crewai_instr`

Auto-instrumentation for CrewAI.

Patches Agent.execute_task, Task.execute, and Crew.kickoff
to automatically create traced spans for each execution.

## Function `patch_crewai()`
Patch CrewAI Agent, Task, and Crew classes for auto-tracing.

