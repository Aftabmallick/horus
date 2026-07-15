"""OpenAI SDK auto-instrumentation.

Monkey-patches openai.chat.completions.create (and async variant)
to automatically capture LLM calls with token/cost tracking.
Supports both standard and streaming (stream=True) responses.
"""

from __future__ import annotations

import functools
from typing import Any, AsyncIterator, Iterator

from agent_tracer_plus.core.context import SpanContext
from agent_tracer_plus.core.models import CostInfo, SpanType, TokenUsage
from agent_tracer_plus.utils.logger import get_logger
from agent_tracer_plus.utils.pricing import get_model_pricing
from agent_tracer_plus.utils.serialization import safe_serialize

logger = get_logger("auto.openai")

_PATCHED = False


def patch_openai() -> None:
    """Patch the OpenAI SDK for auto-tracing."""
    global _PATCHED
    if _PATCHED:
        return

    try:
        from openai.resources.chat import completions as chat_mod

        # Patch sync create
        original_create = chat_mod.Completions.create
        chat_mod.Completions.create = _wrap_sync(original_create)

        # Patch async create
        original_acreate = chat_mod.AsyncCompletions.create
        chat_mod.AsyncCompletions.create = _wrap_async(original_acreate)

        _PATCHED = True
        logger.debug("OpenAI SDK patched successfully (streaming-aware)")
    except Exception as e:
        logger.warning(f"Failed to patch OpenAI: {e}")


def _wrap_sync(original: Any) -> Any:
    """Wrap synchronous completions.create (handles both standard and streaming)."""
    @functools.wraps(original)
    def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
        model = kwargs.get("model", "unknown")
        is_stream = kwargs.get("stream", False)
        span_name = f"openai.chat.completions.create({model})"

        messages = kwargs.get("messages", [])

        if not is_stream:
            # Standard (non-streaming) path
            with SpanContext(name=span_name, span_type=SpanType.LLM) as span:
                span.set_attribute("gen_ai.provider", "openai")
                span.set_attribute("gen_ai.request.model", model)
                span.set_attribute("gen_ai.stream", False)
                span.input = safe_serialize({"model": model, "messages": messages, "temperature": kwargs.get("temperature")})
                try:
                    response = original(self, *args, **kwargs)
                    _extract_response_data(span, response, model)
                    return response
                except Exception as e:
                    span.set_error(e)
                    raise
        else:
            # Streaming path — open span, wrap generator, close on exhaustion
            span_ctx = SpanContext(name=span_name, span_type=SpanType.LLM)
            span = span_ctx.__enter__()
            span.set_attribute("gen_ai.provider", "openai")
            span.set_attribute("gen_ai.request.model", model)
            span.set_attribute("gen_ai.stream", True)
            span.input = safe_serialize({"model": model, "messages": messages, "temperature": kwargs.get("temperature")})

            try:
                raw_stream = original(self, *args, **kwargs)
            except Exception as e:
                span.set_error(e)
                span_ctx.__exit__(type(e), e, e.__traceback__)
                raise

            return _wrap_sync_stream(raw_stream, span, span_ctx, model)

    return wrapper


def _wrap_sync_stream(
    raw_stream: Iterator,
    span: Any,
    span_ctx: Any,
    model: str,
) -> Iterator:
    """Generator that proxies chunks and closes the span on exhaustion."""
    assembled_content = []
    total_input_tokens = 0
    total_output_tokens = 0
    exc_to_raise = None

    try:
        for chunk in raw_stream:
            # Accumulate content from delta
            try:
                delta = chunk.choices[0].delta if chunk.choices else None
                if delta and hasattr(delta, "content") and delta.content:
                    assembled_content.append(delta.content)
                # Some providers include usage in the final chunk
                if hasattr(chunk, "usage") and chunk.usage:
                    total_input_tokens = getattr(chunk.usage, "prompt_tokens", 0)
                    total_output_tokens = getattr(chunk.usage, "completion_tokens", 0)
            except Exception:
                pass
            yield chunk
    except Exception as e:
        span.set_error(e)
        exc_to_raise = e
    finally:
        # Close the span with assembled output
        full_content = "".join(assembled_content)
        span.set_output(safe_serialize({"content": full_content, "stream": True}))
        if total_input_tokens or total_output_tokens:
            total_tokens = total_input_tokens + total_output_tokens
            span.token_usage = TokenUsage(
                input_tokens=total_input_tokens,
                output_tokens=total_output_tokens,
                total_tokens=total_tokens,
            )
            pricing = get_model_pricing(model)
            if pricing:
                cost = pricing.calculate_cost(total_input_tokens, total_output_tokens)
                span.cost_info = CostInfo(total_cost=cost, model=model, pricing_source="auto")
        span_ctx.__exit__(None, None, None)

    if exc_to_raise:
        raise exc_to_raise


def _wrap_async(original: Any) -> Any:
    """Wrap async completions.create (handles both standard and streaming)."""
    @functools.wraps(original)
    async def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
        model = kwargs.get("model", "unknown")
        is_stream = kwargs.get("stream", False)
        span_name = f"openai.chat.completions.create({model})"

        messages = kwargs.get("messages", [])

        if not is_stream:
            with SpanContext(name=span_name, span_type=SpanType.LLM) as span:
                span.set_attribute("gen_ai.provider", "openai")
                span.set_attribute("gen_ai.request.model", model)
                span.set_attribute("gen_ai.stream", False)
                span.input = safe_serialize({"model": model, "messages": messages, "temperature": kwargs.get("temperature")})
                try:
                    response = await original(self, *args, **kwargs)
                    _extract_response_data(span, response, model)
                    return response
                except Exception as e:
                    span.set_error(e)
                    raise
        else:
            # Async streaming path
            span_ctx = SpanContext(name=span_name, span_type=SpanType.LLM)
            span = span_ctx.__enter__()
            span.set_attribute("gen_ai.provider", "openai")
            span.set_attribute("gen_ai.request.model", model)
            span.set_attribute("gen_ai.stream", True)
            span.input = safe_serialize({"model": model, "messages": messages, "temperature": kwargs.get("temperature")})

            try:
                raw_stream = await original(self, *args, **kwargs)
            except Exception as e:
                span.set_error(e)
                span_ctx.__exit__(type(e), e, e.__traceback__)
                raise

            return _wrap_async_stream(raw_stream, span, span_ctx, model)

    return wrapper


async def _wrap_async_stream(
    raw_stream: AsyncIterator,
    span: Any,
    span_ctx: Any,
    model: str,
) -> AsyncIterator:
    """Async generator that proxies chunks and closes the span on exhaustion."""
    assembled_content = []
    total_input_tokens = 0
    total_output_tokens = 0

    try:
        async for chunk in raw_stream:
            try:
                delta = chunk.choices[0].delta if chunk.choices else None
                if delta and hasattr(delta, "content") and delta.content:
                    assembled_content.append(delta.content)
                if hasattr(chunk, "usage") and chunk.usage:
                    total_input_tokens = getattr(chunk.usage, "prompt_tokens", 0)
                    total_output_tokens = getattr(chunk.usage, "completion_tokens", 0)
            except Exception:
                pass
            yield chunk
    except Exception as e:
        span.set_error(e)
        raise
    finally:
        full_content = "".join(assembled_content)
        span.set_output(safe_serialize({"content": full_content, "stream": True}))
        if total_input_tokens or total_output_tokens:
            total_tokens = total_input_tokens + total_output_tokens
            span.token_usage = TokenUsage(
                input_tokens=total_input_tokens,
                output_tokens=total_output_tokens,
                total_tokens=total_tokens,
            )
            pricing = get_model_pricing(model)
            if pricing:
                cost = pricing.calculate_cost(total_input_tokens, total_output_tokens)
                span.cost_info = CostInfo(total_cost=cost, model=model, pricing_source="auto")
        span_ctx.__exit__(None, None, None)

def _extract_response_data(span: Any, response: Any, model: str) -> None:
    """Extract token usage, cost, and output from OpenAI response."""
    try:
        # Output
        if hasattr(response, "choices") and response.choices:
            choice = response.choices[0]
            if hasattr(choice, "message"):
                span.set_output(safe_serialize({"content": choice.message.content, "role": choice.message.role}))
            span.set_attribute("gen_ai.response.finish_reason", getattr(choice, "finish_reason", None))

        # Token usage
        if hasattr(response, "usage") and response.usage:
            usage = response.usage
            span.token_usage = TokenUsage(
                input_tokens=getattr(usage, "prompt_tokens", 0),
                output_tokens=getattr(usage, "completion_tokens", 0),
                total_tokens=getattr(usage, "total_tokens", 0),
            )

            # Cost calculation
            resp_model = getattr(response, "model", model)
            pricing = get_model_pricing(resp_model)
            if pricing:
                cost = pricing.calculate_cost(
                    span.token_usage.input_tokens,
                    span.token_usage.output_tokens,
                )
                span.cost_info = CostInfo(
                    total_cost=cost, model=resp_model, pricing_source="auto",
                )

        span.set_attribute("gen_ai.response.model", getattr(response, "model", model))
    except Exception as e:
        logger.debug(f"Failed to extract OpenAI response data: {e}")

