"""Auto-instrumentation for CrewAI.

Patches Agent.execute_task, Task.execute, and Crew.kickoff
to automatically create traced spans for each execution.
"""

from __future__ import annotations

import functools
import logging
from typing import Any

from agent_tracer_plus.core.context import SpanContext
from agent_tracer_plus.core.models import SpanType

logger = logging.getLogger(__name__)

_patched = False


def patch_crewai() -> None:
    """Patch CrewAI Agent, Task, and Crew classes for auto-tracing."""
    global _patched
    if _patched:
        return

    try:
        from crewai import Agent, Crew, Task
    except ImportError:
        logger.debug("CrewAI not installed, skipping instrumentation.")
        return

    # Patch Agent.execute_task
    if hasattr(Agent, "execute_task"):
        original_execute = Agent.execute_task

        @functools.wraps(original_execute)
        def traced_execute_task(self: Any, *args: Any, **kwargs: Any) -> Any:
            agent_name = getattr(self, "role", "CrewAI-Agent")
            with SpanContext(f"crewai.agent.{agent_name}", span_type=SpanType.AGENT, attributes={
                "crewai.role": agent_name,
                "crewai.goal": getattr(self, "goal", ""),
            }) as span:
                try:
                    result = original_execute(self, *args, **kwargs)
                    span.set_output(str(result)[:2000] if result else None)
                    return result
                except Exception as e:
                    span.set_error(e)
                    raise

        Agent.execute_task = traced_execute_task

    # Patch Task.execute
    if hasattr(Task, "execute"):
        original_task_execute = Task.execute

        @functools.wraps(original_task_execute)
        def traced_task_execute(self: Any, *args: Any, **kwargs: Any) -> Any:
            task_desc = getattr(self, "description", "CrewAI-Task")[:100]
            with SpanContext("crewai.task", span_type=SpanType.CUSTOM, attributes={
                "crewai.task.description": task_desc,
            }) as span:
                try:
                    result = original_task_execute(self, *args, **kwargs)
                    span.set_output(str(result)[:2000] if result else None)
                    return result
                except Exception as e:
                    span.set_error(e)
                    raise

        Task.execute = traced_task_execute

    # Patch Crew.kickoff
    if hasattr(Crew, "kickoff"):
        original_kickoff = Crew.kickoff

        @functools.wraps(original_kickoff)
        def traced_kickoff(self: Any, *args: Any, **kwargs: Any) -> Any:
            with SpanContext("crewai.kickoff", span_type=SpanType.AGENT, attributes={
                "crewai.agents_count": len(getattr(self, "agents", [])),
                "crewai.tasks_count": len(getattr(self, "tasks", [])),
            }) as span:
                try:
                    result = original_kickoff(self, *args, **kwargs)
                    span.set_output(str(result)[:2000] if result else None)
                    return result
                except Exception as e:
                    span.set_error(e)
                    raise

        Crew.kickoff = traced_kickoff

    _patched = True
    logger.info("Successfully instrumented CrewAI.")
