"""Auto-instrumentation for WebSockets."""

import logging
from typing import Any

from agent_tracer_plus import current_trace
from agent_tracer_plus.core.tracer import AgentTracerPlus

logger = logging.getLogger(__name__)


def instrument(tracer: AgentTracerPlus) -> None:
    """Instrument websockets library."""
    try:
        import websockets.protocol
    except ImportError:
        logger.debug("websockets not found, skipping.")
        return

    original_send = websockets.protocol.WebSocketCommonProtocol.send
    original_recv = websockets.protocol.WebSocketCommonProtocol.recv

    async def wrapped_send(self, message, *args, **kwargs):
        trace = current_trace()
        with trace.span("websocket.send", span_type="EXTERNAL") as span:
            span.set_attribute("messaging.system", "websocket")
            span.set_attribute("messaging.operation", "send")
            try:
                if isinstance(message, str):
                    span.input = message
                else:
                    span.input = "<binary data>"
            except Exception:
                pass
                
            try:
                res = await original_send(self, message, *args, **kwargs)
                return res
            except Exception as e:
                span.set_attribute("error", True)
                span.set_attribute("error.message", str(e))
                raise

    async def wrapped_recv(self, *args, **kwargs):
        trace = current_trace()
        with trace.span("websocket.receive", span_type="EXTERNAL") as span:
            span.set_attribute("messaging.system", "websocket")
            span.set_attribute("messaging.operation", "receive")
            try:
                res = await original_recv(self, *args, **kwargs)
                if isinstance(res, str):
                    span.output = res
                else:
                    span.output = "<binary data>"
                return res
            except Exception as e:
                span.set_attribute("error", True)
                span.set_attribute("error.message", str(e))
                raise

    websockets.protocol.WebSocketCommonProtocol.send = wrapped_send
    websockets.protocol.WebSocketCommonProtocol.recv = wrapped_recv
