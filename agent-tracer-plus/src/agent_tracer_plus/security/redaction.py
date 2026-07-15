"""PII redaction using regex patterns."""

import re
from re import Pattern
from typing import Any, Dict, Union


class PIIRedactor:
    """Scrub sensitive information from payloads before storage."""

    # Default regex patterns for common PII
    DEFAULT_PATTERNS = {
        "EMAIL": re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
        "SSN": re.compile(r'\b\d{3}-\d{2}-\d{4}\b'),
        "CREDIT_CARD": re.compile(r'\b(?:\d{4}[ -]?){3}\d{4}\b'),
        "PHONE": re.compile(r'\b\+?1?\s*\(?-*\d{3}\)?\s*-*\d{3}\s*-*\d{4}\b'),
    }

    def __init__(self, patterns: Dict[str, Union[str, Pattern]] = None):
        self.patterns = dict(self.DEFAULT_PATTERNS)
        if patterns:
            for name, pattern in patterns.items():
                if isinstance(pattern, str):
                    self.patterns[name] = re.compile(pattern)
                else:
                    self.patterns[name] = pattern

    def redact_text(self, text: str) -> str:
        """Apply all regex patterns to replace matches with [REDACTED:<type>]."""
        if not isinstance(text, str):
            return text

        redacted = text
        for name, pattern in self.patterns.items():
            redacted = pattern.sub(f"[REDACTED:{name}]", redacted)
        return redacted

    def redact_payload(self, payload: Any) -> Any:
        """Recursively scrub strings within a dictionary or list."""
        if isinstance(payload, str):
            return self.redact_text(payload)
        elif isinstance(payload, dict):
            return {k: self.redact_payload(v) for k, v in payload.items()}
        elif isinstance(payload, list):
            return [self.redact_payload(v) for v in payload]
        return payload
