"""Auto-instrumentation for AutoGen.

Patches ConversableAgent.generate_reply and initiate_chat
for automatic trace span creation.
"""

from __future__ import annotations

import functools
import logging
from typing import Any, Dict

from agent_tracer_plus.core.context import SpanContext
from agent_tracer_plus.core.models import SpanType
from agent_tracer_plus.utils.serialization import safe_serialize

logger = logging.getLogger(__name__)

_patched = False


def _extract_messages(messages: list) -> str:
    """Extract string representation of a list of messages."""
    if not messages:
        return ""
    if isinstance(messages, str):
        return messages
    if isinstance(messages, list):
        try:
            return "\\n".join([str(m.get("content", m)) if isinstance(m, dict) else str(m) for m in messages])
        except Exception:
            pass
    return str(messages)


def patch_autogen() -> None:
    """Patch AutoGen ConversableAgent for auto-tracing."""
    global _patched
    if _patched:
        return

    try:
        from autogen import ConversableAgent
        import autogen.agentchat
    except ImportError:
        logger.debug("AutoGen not installed, skipping instrumentation.")
        return

    # Patch generate_reply
    if hasattr(ConversableAgent, "generate_reply"):
        original_generate = ConversableAgent.generate_reply

        @functools.wraps(original_generate)
        def traced_generate_reply(self: Any, messages: Any = None, sender: Any = None, **kwargs: Any) -> Any:
            agent_name = getattr(self, "name", "AutoGen-Agent")
            sender_name = getattr(sender, "name", "Unknown") if sender else "Unknown"
            
            with SpanContext(f"autogen.{agent_name}.generate_reply", span_type=SpanType.AGENT, attributes={
                "autogen.agent_name": agent_name,
                "autogen.sender": sender_name,
                "autogen.operation": "generate_reply",
            }) as span:
                if messages:
                    span.input = _extract_messages(messages)
                
                try:
                    result = original_generate(self, messages=messages, sender=sender, **kwargs)
                    
                    if isinstance(result, tuple) and len(result) >= 2:
                        # AutoGen generate_reply often returns (bool, reply)
                        is_final, reply = result[0], result[1]
                        span.set_attribute("autogen.is_final", is_final)
                        span.set_output(str(reply) if reply else None)
                    else:
                        span.set_output(str(result) if result else None)
                    return result
                except Exception as e:
                    span.set_error(e)
                    raise

        ConversableAgent.generate_reply = traced_generate_reply

    # Patch initiate_chat
    if hasattr(ConversableAgent, "initiate_chat"):
        original_chat = ConversableAgent.initiate_chat

        @functools.wraps(original_chat)
        def traced_initiate_chat(self: Any, *args: Any, **kwargs: Any) -> Any:
            agent_name = getattr(self, "name", "AutoGen-Agent")
            recipient = args[0] if args else kwargs.get("recipient")
            recipient_name = getattr(recipient, "name", "Unknown") if recipient else "Unknown"

            with SpanContext(f"autogen.chat.{agent_name}->{recipient_name}", span_type=SpanType.WORKFLOW, attributes={
                "autogen.initiator": agent_name,
                "autogen.recipient": recipient_name,
                "autogen.operation": "initiate_chat",
            }) as span:
                
                message = kwargs.get("message")
                if message:
                    span.input = str(message)
                
                try:
                    result = original_chat(self, *args, **kwargs)
                    
                    if hasattr(result, "chat_history"):
                        span.set_attribute("autogen.chat_turns", len(result.chat_history))
                        span.set_output(_extract_messages(result.chat_history))
                    elif hasattr(result, "summary"):
                        span.set_output(str(result.summary))
                    else:
                        span.set_output(str(result)[:2000] if result else None)
                        
                    if hasattr(result, "cost"):
                        span.set_attribute("autogen.cost", safe_serialize(result.cost))
                        
                    return result
                except Exception as e:
                    span.set_error(e)
                    raise

        ConversableAgent.initiate_chat = traced_initiate_chat

    _patched = True
    logger.info("Successfully instrumented AutoGen.")

