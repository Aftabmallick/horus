"""Auto-instrumentation for LangChain."""

import logging
from typing import Any

from agent_tracer_plus import current_trace
from agent_tracer_plus.core.tracer import AgentTracerPlus

logger = logging.getLogger(__name__)


def instrument(tracer: AgentTracerPlus) -> None:
    """Instrument LangChain by registering a global callback handler."""
    try:
        import langchain
        from langchain.callbacks.base import BaseCallbackHandler
        from langchain.callbacks.manager import set_handler
    except ImportError:
        logger.debug("LangChain not found, skipping instrumentation.")
        return

    class AgentTracerCallbackHandler(BaseCallbackHandler):
        """Callback handler that translates LangChain events to Agent Tracer spans."""

        def __init__(self):
            super().__init__()
            self._spans = {}

        def on_llm_start(self, serialized: dict, prompts: list, **kwargs: Any) -> Any:
            """Run when LLM starts running."""
            run_id = kwargs.get("run_id")
            if not run_id:
                return

            trace = current_trace()
            span = trace.span("langchain.llm", span_type="LLM")
            span.__enter__()
            self._spans[str(run_id)] = span

            model = kwargs.get("invocation_params", {}).get("model_name", "unknown")
            span.set_attribute("model", model)
            if prompts:
                span.set_attribute("prompt", prompts[0])

        def on_llm_end(self, response: Any, **kwargs: Any) -> Any:
            """Run when LLM ends running."""
            run_id = kwargs.get("run_id")
            if not run_id or str(run_id) not in self._spans:
                return

            span = self._spans.pop(str(run_id))
            try:
                generations = response.generations
                if generations and generations[0]:
                    span.set_attribute("completion", generations[0][0].text)

                llm_output = response.llm_output or {}
                token_usage = llm_output.get("token_usage", {})
                if token_usage:
                    span.set_attribute("prompt_tokens", token_usage.get("prompt_tokens", 0))
                    span.set_attribute("completion_tokens", token_usage.get("completion_tokens", 0))
            finally:
                span.__exit__(None, None, None)

        def on_llm_error(self, error: BaseException, **kwargs: Any) -> Any:
            """Run when LLM errors."""
            run_id = kwargs.get("run_id")
            if not run_id or str(run_id) not in self._spans:
                return

            span = self._spans.pop(str(run_id))
            span.__exit__(type(error), error, error.__traceback__)

        def on_chain_start(self, serialized: dict, inputs: dict, **kwargs: Any) -> Any:
            run_id = kwargs.get("run_id")
            if not run_id:
                return
            trace = current_trace()
            chain_name = serialized.get("name", "chain")
            span = trace.span(f"langchain.chain.{chain_name}", span_type="STEP")
            span.__enter__()
            span.set_attribute("inputs", inputs)
            self._spans[str(run_id)] = span

        def on_chain_end(self, outputs: dict, **kwargs: Any) -> Any:
            run_id = kwargs.get("run_id")
            if not run_id or str(run_id) not in self._spans:
                return
            span = self._spans.pop(str(run_id))
            span.set_attribute("outputs", outputs)
            span.__exit__(None, None, None)

        def on_chain_error(self, error: BaseException, **kwargs: Any) -> Any:
            run_id = kwargs.get("run_id")
            if not run_id or str(run_id) not in self._spans:
                return
            span = self._spans.pop(str(run_id))
            span.__exit__(type(error), error, error.__traceback__)

        def on_tool_start(self, serialized: dict, input_str: str, **kwargs: Any) -> Any:
            run_id = kwargs.get("run_id")
            if not run_id:
                return
            trace = current_trace()
            tool_name = serialized.get("name", "tool")
            span = trace.span(f"langchain.tool.{tool_name}", span_type="TOOL")
            span.__enter__()
            span.set_attribute("input", input_str)
            self._spans[str(run_id)] = span

        def on_tool_end(self, output: str, **kwargs: Any) -> Any:
            run_id = kwargs.get("run_id")
            if not run_id or str(run_id) not in self._spans:
                return
            span = self._spans.pop(str(run_id))
            span.set_attribute("output", output)
            span.__exit__(None, None, None)

        def on_tool_error(self, error: BaseException, **kwargs: Any) -> Any:
            run_id = kwargs.get("run_id")
            if not run_id or str(run_id) not in self._spans:
                return
            span = self._spans.pop(str(run_id))
            span.__exit__(type(error), error, error.__traceback__)

    set_handler(AgentTracerCallbackHandler())
    logger.debug("Successfully instrumented LangChain.")
