"""Auto-instrumentation for Celery."""

import logging

from agent_tracer_plus import current_trace
from agent_tracer_plus.core.tracer import AgentTracerPlus
from agent_tracer_plus.propagation.w3c import extract_context, inject_context

logger = logging.getLogger(__name__)


def instrument(tracer: AgentTracerPlus) -> None:
    """Instrument Celery by connecting to signals."""
    try:
        import celery.signals
    except ImportError:
        logger.debug("Celery not found, skipping instrumentation.")
        return

    _task_spans = {}

    @celery.signals.before_task_publish.connect
    def before_task_publish(sender=None, headers=None, body=None, **kwargs):
        """Inject trace context before task is published."""
        trace = current_trace()
        if trace:
            # Create a span for the publish event
            span = trace.span(f"celery.publish.{sender}", span_type="STEP")
            span.__enter__()
            headers.update(inject_context({}))
            span.__exit__(None, None, None)

    @celery.signals.task_prerun.connect
    def task_prerun(task_id=None, task=None, request=None, **kwargs):
        """Extract trace context and start a span when task runs."""
        headers = request.headers if request else {}
        ctx = extract_context(headers)

        trace = current_trace()
        if ctx:
            trace = trace.continue_from(ctx, name=f"celery.task.{task.name}")
        else:
            span = trace.span(f"celery.task.{task.name}", span_type="STEP")

        span = trace.current_span
        if span:
            span.__enter__()
            span.set_attribute("task_id", task_id)
            _task_spans[task_id] = span

    @celery.signals.task_postrun.connect
    def task_postrun(task_id=None, task=None, retval=None, state=None, **kwargs):
        """End the task span."""
        span = _task_spans.pop(task_id, None)
        if span:
            span.set_attribute("state", state)
            span.__exit__(None, None, None)

    @celery.signals.task_failure.connect
    def task_failure(task_id=None, exception=None, traceback=None, **kwargs):
        """Record task failure."""
        span = _task_spans.get(task_id)
        if span:
            span.__exit__(type(exception), exception, traceback)

    logger.debug("Successfully instrumented Celery.")
