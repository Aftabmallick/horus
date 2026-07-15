"""PII Masking module for Agent Tracer Plus."""

import re
from typing import Any, Dict, List, Optional, Union

from agent_tracer_plus.core.models import Span, Trace

# Simple regexes for MVP PII masking
PII_PATTERNS = {
    "EMAIL": re.compile(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+'),
    "PHONE": re.compile(r'\b(?:\+?1[-. ]?)?\(?([0-9]{3})\)?[-. ]?([0-9]{3})[-. ]?([0-9]{4})\b'),
    "CREDIT_CARD": re.compile(r'\b(?:\d[ -]*?){13,16}\b'),
    "SSN": re.compile(r'\b(?!000|666)[0-8][0-9]{2}-(?!00)[0-9]{2}-(?!0000)[0-9]{4}\b'),
}

class PIIMasker:
    """Masks Personally Identifiable Information in traces and spans."""

    def __init__(self, custom_patterns: Optional[Dict[str, re.Pattern]] = None):
        self.patterns = PII_PATTERNS.copy()
        if custom_patterns:
            self.patterns.update(custom_patterns)

    def scrub_text(self, text: str) -> str:
        """Apply all regex patterns to replace sensitive data with [REDACTED]."""
        if not isinstance(text, str):
            return text
        scrubbed = text
        for label, pattern in self.patterns.items():
            scrubbed = pattern.sub(f"[{label}_REDACTED]", scrubbed)
        return scrubbed

    def scrub_data(self, data: Any) -> Any:
        """Recursively scrub data structures (dicts, lists, strings)."""
        if isinstance(data, str):
            return self.scrub_text(data)
        elif isinstance(data, dict):
            return {k: self.scrub_data(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self.scrub_data(item) for item in data]
        return data

    def mask_span(self, span: Span) -> None:
        """Scrub inputs, outputs, and attributes of a span in-place."""
        if span.input is not None:
            span.input = self.scrub_data(span.input)
        if span.output is not None:
            span.output = self.scrub_data(span.output)
        
        # Scrub error message if present
        if span.error and isinstance(span.error, dict):
            if "message" in span.error and isinstance(span.error["message"], str):
                span.error["message"] = self.scrub_text(span.error["message"])
                
        # Attributes often contain prompt templates or partial data
        if span.attributes:
            span.attributes = self.scrub_data(span.attributes)

    def mask_trace(self, trace: Trace) -> None:
        """Scrub trace metadata and all attached spans in-place."""
        if trace.metadata:
            trace.metadata = self.scrub_data(trace.metadata)
        
        for span in trace.spans:
            self.mask_span(span)
