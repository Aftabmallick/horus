import logging
from typing import Any, Callable

from agent_tracer_plus.auto.patcher import wrap
from agent_tracer_plus.core.context import SpanContext
from agent_tracer_plus.core.models import SpanType, TokenUsage

logger = logging.getLogger(__name__)

def patch_agno() -> None:
    """Patch Agno (formerly Phidata) Agent.run method to capture traces."""
    try:
        from agno.agent import Agent
    except ImportError:
        logger.debug("Agno is not installed. Skipping patch.")
        return

    original_run = getattr(Agent, "run", None)
    if not original_run:
        return

    def run_wrapper(self_obj: Any, *args, **kwargs) -> Any:
        agent_name = getattr(self_obj, "name", "AgnoAgent")
        print(f"[*] agno_instr: run_wrapper called for agent {agent_name}")
        # Start a child span for this agent run
        with SpanContext(
            name=agent_name,
            span_type=SpanType.AGENT,
            attributes={
                "agno.agent.name": agent_name,
                "agno.agent.model": str(getattr(self_obj, "model", "")),
                "agno.agent.instructions": str(getattr(self_obj, "instructions", "")),
            }
        ) as span:
            print(f"[*] agno_instr: span created {span.span_id}")
            # Capture the input (first positional arg or 'message' kwarg)
            input_message = args[0] if args else kwargs.get("message", None)
            if input_message:
                span.input = {"message": input_message}
                
            # Execute original function
            result = original_run(self_obj, *args, **kwargs)
            print(f"[*] agno_instr: original_run finished")
            
            # Capture output
            if result:
                # Assuming result is a RunResponse or string
                output_content = getattr(result, "content", str(result))
                span.set_output({"content": output_content})
                
                # Check for token metrics if available on the model/run
                metrics = getattr(result, "metrics", None)
                if metrics:
                    prompt_tokens = getattr(metrics, "prompt_tokens", 0)
                    completion_tokens = getattr(metrics, "completion_tokens", 0)
                    total_tokens = getattr(metrics, "total_tokens", 0)
                    if total_tokens > 0:
                        span.token_usage = TokenUsage(
                            input_tokens=prompt_tokens,
                            output_tokens=completion_tokens,
                            total_tokens=total_tokens
                        )
                
            print(f"[*] agno_instr: returning result, span will close")
            return result

    wrap(
        target=Agent,
        method_name="run",
        wrapper=run_wrapper
    )
    logger.debug("Patched agno.agent.Agent.run")

def instrument(tracer: Any = None) -> None:
    patch_agno()
