# Module: `agent_tracer_plus.auto.openai_instr`

OpenAI SDK auto-instrumentation.

Monkey-patches openai.chat.completions.create (and async variant)
to automatically capture LLM calls with token/cost tracking.
Supports both standard and streaming (stream=True) responses.

## Function `patch_openai()`
Patch the OpenAI SDK for auto-tracing.

## Function `_wrap_sync(original)`
Wrap synchronous completions.create (handles both standard and streaming).

## Function `_wrap_sync_stream(raw_stream, span, span_ctx, model)`
Generator that proxies chunks and closes the span on exhaustion.

## Function `_wrap_async(original)`
Wrap async completions.create (handles both standard and streaming).

## Function `_extract_response_data(span, response, model)`
Extract token usage, cost, and output from OpenAI response.

