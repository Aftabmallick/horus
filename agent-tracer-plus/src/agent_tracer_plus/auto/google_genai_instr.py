"""Auto-instrumentation for google-genai (Gemini)."""

import logging
from typing import Any, Callable

from agent_tracer_plus import current_trace, trace_block
from agent_tracer_plus.core.tracer import AgentTracerPlus

logger = logging.getLogger(__name__)


def instrument(tracer: AgentTracerPlus) -> None:
    """Instrument google-genai library."""
    try:
        import google.genai.models
        from google.genai.types import GenerateContentResponse
    except ImportError:
        logger.debug("google-genai not found, skipping instrumentation.")
        return

    original_generate_content = google.genai.models.Models.generate_content
    original_generate_content_async = google.genai.models.AsyncModels.generate_content

    def _extract_text(contents: Any) -> str:
        # Simplistic extraction of prompt text for span input
        if isinstance(contents, str):
            return contents
        if isinstance(contents, list):
            res = []
            for c in contents:
                if hasattr(c, "parts"):
                    for p in c.parts:
                        if hasattr(p, "text") and p.text:
                            res.append(p.text)
                elif isinstance(c, str):
                    res.append(c)
            return "\\n".join(res)
        return str(contents)

    def _extract_response_attributes(response: GenerateContentResponse, span) -> None:
        if hasattr(response, "text"):
            span.output = response.text
        if hasattr(response, "usage_metadata"):
            usage = response.usage_metadata
            if hasattr(usage, "prompt_token_count"):
                span.set_attribute("llm.prompt_tokens", usage.prompt_token_count)
            if hasattr(usage, "candidates_token_count"):
                span.set_attribute("llm.completion_tokens", usage.candidates_token_count)
            if hasattr(usage, "total_token_count"):
                span.set_attribute("llm.total_tokens", usage.total_token_count)

    def wrapped_generate_content(self, *args, **kwargs):
        model_name = kwargs.get("model", args[0] if args else "unknown")
        
        with trace_block("google_genai.generate_content", span_type="LLM") as span:
            span.set_attribute("llm.model", str(model_name))
            span.set_attribute("llm.provider", "google")
            
            contents = kwargs.get("contents", args[1] if len(args) > 1 else None)
            if contents:
                span.input = _extract_text(contents)
                
            if "config" in kwargs:
                span.set_attribute("llm.request_config", str(kwargs["config"]))

            try:
                response = original_generate_content(self, *args, **kwargs)
                _extract_response_attributes(response, span)
                return response
            except Exception as e:
                span.set_attribute("error", True)
                span.set_attribute("error.message", str(e))
                raise

    async def wrapped_generate_content_async(self, *args, **kwargs):
        model_name = kwargs.get("model", args[0] if args else "unknown")
        
        with trace_block("google_genai.generate_content_async", span_type="LLM") as span:
            span.set_attribute("llm.model", str(model_name))
            span.set_attribute("llm.provider", "google")
            
            contents = kwargs.get("contents", args[1] if len(args) > 1 else None)
            if contents:
                span.input = _extract_text(contents)

            if "config" in kwargs:
                span.set_attribute("llm.request_config", str(kwargs["config"]))

            try:
                response = await original_generate_content_async(self, *args, **kwargs)
                _extract_response_attributes(response, span)
                return response
            except Exception as e:
                span.set_attribute("error", True)
                span.set_attribute("error.message", str(e))
                raise

    google.genai.models.Models.generate_content = wrapped_generate_content
    google.genai.models.AsyncModels.generate_content = wrapped_generate_content_async
    logger.debug("Successfully instrumented google-genai.")
