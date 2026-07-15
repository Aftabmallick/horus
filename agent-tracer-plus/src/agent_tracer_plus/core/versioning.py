"""Prompt Versioning Manager for Agent Tracer Plus."""

import hashlib
from typing import Any, Dict


class PromptVersionTracker:
    """Tracks prompt templates by hashing them to auto-detect versions."""

    _cache: Dict[str, str] = {}

    @classmethod
    def get_version(cls, template: str) -> str:
        """Hash a template string to get its version ID (e.g. v_a1b2c3d4)."""
        if not template:
            return "v_unknown"

        if template in cls._cache:
            return cls._cache[template]

        # Create a short hash
        h = hashlib.sha256(template.encode("utf-8")).hexdigest()[:8]
        version = f"v_{h}"
        cls._cache[template] = version
        return version

def track_prompt(template: str, span: Any) -> str:
    """Helper to track prompt and attach version to a span."""
    version = PromptVersionTracker.get_version(template)
    span.set_attribute("prompt.version", version)
    return version
