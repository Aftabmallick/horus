"""Anthropic SDK auto-instrumentation."""

from __future__ import annotations

import functools
from typing import Any

from agent_tracer_plus.core.context import SpanContext
from agent_tracer_plus.core.models import CostInfo, SpanType, TokenUsage
from agent_tracer_plus.utils.logger import get_logger
from agent_tracer_plus.utils.pricing import get_model_pricing
from agent_tracer_plus.utils.serialization import safe_serialize

logger = get_logger("auto.anthropic")
_PATCHED = False

def patch_anthropic() -> None:
    global _PATCHED
    if _PATCHED:
        return
    try:
        import anthropic
        orig_create = anthropic.Anthropic.messages.create.__func__ if hasattr(anthropic.Anthropic, 'messages') else None
        if orig_create is None:
            from anthropic.resources import messages as msg_mod
            orig_sync = msg_mod.Messages.create
            msg_mod.Messages.create = _wrap_sync(orig_sync)
            orig_async = msg_mod.AsyncMessages.create
            msg_mod.AsyncMessages.create = _wrap_async(orig_async)
        _PATCHED = True
        logger.debug("Anthropic SDK patched successfully")
    except Exception as e:
        logger.warning(f"Failed to patch Anthropic: {e}")

def _wrap_sync(original: Any) -> Any:
    @functools.wraps(original)
    def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
        model = kwargs.get("model", "unknown")
        is_stream = kwargs.get("stream", False)
        
        if not is_stream:
            with SpanContext(name=f"anthropic.messages.create({model})", span_type=SpanType.LLM) as span:
                span.set_attribute("gen_ai.provider", "anthropic")
                span.set_attribute("gen_ai.request.model", model)
                span.input = safe_serialize({"model": model, "messages": kwargs.get("messages", [])})
                try:
                    response = original(self, *args, **kwargs)
                    _extract(span, response, model)
                    return response
                except Exception as e:
                    span.set_error(e)
                    raise
        else:
            span_ctx = SpanContext(name=f"anthropic.messages.create({model})", span_type=SpanType.LLM)
            span = span_ctx.__enter__()
            span.set_attribute("gen_ai.provider", "anthropic")
            span.set_attribute("gen_ai.request.model", model)
            span.input = safe_serialize({"model": model, "messages": kwargs.get("messages", [])})
            try:
                raw_stream = original(self, *args, **kwargs)
            except Exception as e:
                span.set_error(e)
                span_ctx.__exit__(type(e), e, e.__traceback__)
                raise
            return _wrap_anthropic_stream(raw_stream, span, span_ctx, model)
    return wrapper

def _wrap_async(original: Any) -> Any:
    @functools.wraps(original)
    async def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
        model = kwargs.get("model", "unknown")
        is_stream = kwargs.get("stream", False)
        
        if not is_stream:
            with SpanContext(name=f"anthropic.messages.create({model})", span_type=SpanType.LLM) as span:
                span.set_attribute("gen_ai.provider", "anthropic")
                span.set_attribute("gen_ai.request.model", model)
                span.input = safe_serialize({"model": model, "messages": kwargs.get("messages", [])})
                try:
                    response = await original(self, *args, **kwargs)
                    _extract(span, response, model)
                    return response
                except Exception as e:
                    span.set_error(e)
                    raise
        else:
            span_ctx = SpanContext(name=f"anthropic.messages.create({model})", span_type=SpanType.LLM)
            span = span_ctx.__enter__()
            span.set_attribute("gen_ai.provider", "anthropic")
            span.set_attribute("gen_ai.request.model", model)
            span.input = safe_serialize({"model": model, "messages": kwargs.get("messages", [])})
            try:
                raw_stream = await original(self, *args, **kwargs)
            except Exception as e:
                span.set_error(e)
                span_ctx.__exit__(type(e), e, e.__traceback__)
                raise
            return _wrap_anthropic_async_stream(raw_stream, span, span_ctx, model)
    return wrapper

def _wrap_anthropic_stream(raw_stream: Any, span: Any, span_ctx: Any, model: str) -> Any:
    """Generator that proxies Anthropic sync stream chunks."""
    assembled_content = []
    input_tokens = 0
    output_tokens = 0
    try:
        for event in raw_stream:
            if hasattr(event, 'delta') and hasattr(event.delta, 'text'):
                assembled_content.append(event.delta.text)
            if hasattr(event, 'usage'):
                input_tokens = getattr(event.usage, 'input_tokens', 0)
                output_tokens = getattr(event.usage, 'output_tokens', 0)
            elif hasattr(event, 'message') and hasattr(event.message, 'usage'):
                input_tokens = getattr(event.message.usage, 'input_tokens', 0)
                output_tokens = getattr(event.message.usage, 'output_tokens', 0)
            yield event
    except Exception as e:
        span.set_error(e)
        raise
    finally:
        span.set_output(safe_serialize({"content": "".join(assembled_content), "stream": True}))
        if input_tokens or output_tokens:
            span.token_usage = TokenUsage(input_tokens=input_tokens, output_tokens=output_tokens, total_tokens=input_tokens+output_tokens)
            pricing = get_model_pricing(model)
            if pricing:
                span.cost_info = CostInfo(
                    total_cost=pricing.calculate_cost(input_tokens, output_tokens),
                    model=model, pricing_source="auto"
                )
        span_ctx.__exit__(None, None, None)

async def _wrap_anthropic_async_stream(raw_stream: Any, span: Any, span_ctx: Any, model: str) -> Any:
    """Async generator that proxies Anthropic async stream chunks."""
    assembled_content = []
    input_tokens = 0
    output_tokens = 0
    try:
        async for event in raw_stream:
            if hasattr(event, 'delta') and hasattr(event.delta, 'text'):
                assembled_content.append(event.delta.text)
            if hasattr(event, 'usage'):
                input_tokens = getattr(event.usage, 'input_tokens', 0)
                output_tokens = getattr(event.usage, 'output_tokens', 0)
            elif hasattr(event, 'message') and hasattr(event.message, 'usage'):
                input_tokens = getattr(event.message.usage, 'input_tokens', 0)
                output_tokens = getattr(event.message.usage, 'output_tokens', 0)
            yield event
    except Exception as e:
        span.set_error(e)
        raise
    finally:
        span.set_output(safe_serialize({"content": "".join(assembled_content), "stream": True}))
        if input_tokens or output_tokens:
            span.token_usage = TokenUsage(input_tokens=input_tokens, output_tokens=output_tokens, total_tokens=input_tokens+output_tokens)
            pricing = get_model_pricing(model)
            if pricing:
                span.cost_info = CostInfo(
                    total_cost=pricing.calculate_cost(input_tokens, output_tokens),
                    model=model, pricing_source="auto"
                )
        span_ctx.__exit__(None, None, None)

def _extract(span: Any, response: Any, model: str) -> None:
    try:
        if hasattr(response, "content") and response.content:
            span.set_output(safe_serialize({"content": [c.text for c in response.content if hasattr(c, 'text')]}))
        if hasattr(response, "usage"):
            u = response.usage
            span.token_usage = TokenUsage(
                input_tokens=getattr(u, "input_tokens", 0),
                output_tokens=getattr(u, "output_tokens", 0),
            )
            pricing = get_model_pricing(getattr(response, "model", model))
            if pricing:
                span.cost_info = CostInfo(
                    total_cost=pricing.calculate_cost(span.token_usage.input_tokens, span.token_usage.output_tokens),
                    model=model, pricing_source="auto",
                )
    except Exception as e:
        logger.debug(f"Failed to extract Anthropic response: {e}")
