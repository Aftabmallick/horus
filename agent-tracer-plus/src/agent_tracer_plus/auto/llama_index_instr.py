"""Auto-instrumentation for LlamaIndex."""

import logging
from typing import Any

from agent_tracer_plus import current_trace
from agent_tracer_plus.core.tracer import AgentTracerPlus

logger = logging.getLogger(__name__)


def instrument(tracer: AgentTracerPlus) -> None:
    """Instrument LlamaIndex via its global callback manager."""
    try:
        from llama_index.core import Settings
        from llama_index.core.callbacks.base_handler import BaseCallbackHandler
        from llama_index.core.callbacks.schema import CBEventType, EventPayload
    except ImportError:
        logger.debug("LlamaIndex not found, skipping instrumentation.")
        return

    class AgentTracerLlamaIndexHandler(BaseCallbackHandler):
        """Callback handler for LlamaIndex events."""

        def __init__(self):
            super().__init__(event_starts_to_ignore=[], event_ends_to_ignore=[])
            self._spans = {}

        def on_event_start(
            self,
            event_type: CBEventType,
            payload: dict[str, Any] | None = None,
            event_id: str = "",
            parent_id: str = "",
            **kwargs: Any,
        ) -> str:
            trace = current_trace()
            span_type = "STEP"
            if event_type == CBEventType.LLM:
                span_type = "LLM"
            elif event_type == CBEventType.RETRIEVE:
                span_type = "RETRIEVAL"
            elif event_type == CBEventType.FUNCTION_CALL:
                span_type = "TOOL"
            elif event_type == CBEventType.EMBEDDING:
                span_type = "EMBEDDING"

            span = trace.span(f"llama_index.{event_type.value}", span_type=span_type)
            span.__enter__()
            self._spans[event_id] = span

            if payload:
                if EventPayload.QUERY_STR in payload:
                    span.input = payload[EventPayload.QUERY_STR]
                elif EventPayload.MESSAGES in payload:
                    # Try to capture last message as input
                    msgs = payload[EventPayload.MESSAGES]
                    if msgs:
                        span.input = str(msgs[-1])
                elif EventPayload.PROMPT in payload:
                    span.input = str(payload[EventPayload.PROMPT])
                
                # Capture everything else as attributes
                for k, v in payload.items():
                    if k in (EventPayload.QUERY_STR, EventPayload.MESSAGES, EventPayload.PROMPT):
                        continue
                    try:
                        span.set_attribute(f"llama_index.{k}", str(v))
                    except Exception:
                        pass

            return event_id

        def on_event_end(
            self,
            event_type: CBEventType,
            payload: dict[str, Any] | None = None,
            event_id: str = "",
            **kwargs: Any,
        ) -> None:
            if event_id not in self._spans:
                return

            span = self._spans.pop(event_id)
            if payload:
                if EventPayload.RESPONSE in payload:
                    span.output = str(payload[EventPayload.RESPONSE])
                elif EventPayload.NODES in payload:
                    nodes = payload[EventPayload.NODES]
                    span.output = "\\n---\\n".join([str(n.node.get_content()) for n in nodes if hasattr(n, 'node')])
                    span.set_attribute("llama_index.node_count", len(nodes))
                elif EventPayload.COMPLETION in payload:
                    span.output = str(payload[EventPayload.COMPLETION])

                for k, v in payload.items():
                    if k in (EventPayload.RESPONSE, EventPayload.NODES, EventPayload.COMPLETION):
                        continue
                    try:
                        span.set_attribute(f"llama_index.{k}", str(v))
                    except Exception:
                        pass
                        
            span.__exit__(None, None, None)

        def start_trace(self, trace_id: str | None = None) -> None:
            pass

        def end_trace(
            self,
            trace_id: str | None = None,
            trace_map: dict[str, list[str]] | None = None,
        ) -> None:
            pass

    if Settings.callback_manager:
        Settings.callback_manager.add_handler(AgentTracerLlamaIndexHandler())
        logger.debug("Successfully instrumented LlamaIndex.")

