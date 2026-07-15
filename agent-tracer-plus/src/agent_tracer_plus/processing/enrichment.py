"""Enrichment processing for traces."""

import hashlib
import logging
from typing import Dict

from agent_tracer_plus.core.models import Span, Trace

logger = logging.getLogger(__name__)


class PromptVersionTracker:
    """Tracks prompt templates and versions them."""

    def __init__(self):
        self._prompt_hashes: Dict[str, str] = {}

    def _hash_prompt(self, template: str) -> str:
        return hashlib.sha256(template.encode('utf-8')).hexdigest()[:8]

    def get_version(self, template: str) -> str:
        """Get or create a version hash for a prompt template."""
        h = self._hash_prompt(template)
        if h not in self._prompt_hashes:
            self._prompt_hashes[h] = template
        return f"v_{h}"


class TraceEnricher:
    """Enriches traces with derived data."""

    def __init__(self):
        self.prompt_tracker = PromptVersionTracker()

    def enrich_span(self, span: Span) -> None:
        """Enrich a single span in-place."""
        # Auto-version prompts
        if span.span_type == "LLM" and "prompt_template" in span.attributes:
            template = span.attributes["prompt_template"]
            version = self.prompt_tracker.get_version(template)
            span.set_attribute("prompt_version", version)

    def enrich_trace(self, trace: Trace, spans: list[Span]) -> None:
        """Enrich a trace and its spans."""
        total_cost = 0.0
        total_tokens = 0

        for span in spans:
            self.enrich_span(span)

            # Aggregate metrics to trace level
            if span.span_type == "LLM":
                # In a real system, calculate cost based on model pricing table
                tokens = span.attributes.get("total_tokens", 0)
                cost = span.attributes.get("cost", 0.0)
                total_tokens += int(tokens)
                total_cost += float(cost)

        trace.set_attribute("total_tokens", total_tokens)
        trace.set_attribute("total_cost", total_cost)
