"""W3C Baggage propagation.

Carries application-defined key-value pairs across service boundaries.
See: https://www.w3.org/TR/baggage/
"""

from __future__ import annotations

import urllib.parse
from typing import Dict, Optional

from agent_tracer_plus.utils.logger import get_logger

logger = get_logger("propagation.baggage")

# Max baggage header size per spec
_MAX_HEADER_SIZE = 8192
_MAX_ENTRIES = 180


class Baggage:
    """In-memory baggage container (key-value pairs)."""

    def __init__(self, entries: Optional[Dict[str, str]] = None):
        self._entries: Dict[str, str] = dict(entries) if entries else {}

    def get(self, key: str) -> Optional[str]:
        """Get a baggage value by key."""
        return self._entries.get(key)

    def set(self, key: str, value: str) -> None:
        """Set a baggage key-value pair."""
        if len(self._entries) >= _MAX_ENTRIES:
            logger.warning(f"Baggage entry limit ({_MAX_ENTRIES}) reached, dropping key '{key}'")
            return
        self._entries[key] = value

    def remove(self, key: str) -> None:
        """Remove a baggage entry."""
        self._entries.pop(key, None)

    @property
    def entries(self) -> Dict[str, str]:
        """Get all baggage entries."""
        return dict(self._entries)

    def __len__(self) -> int:
        return len(self._entries)

    def __repr__(self) -> str:
        return f"Baggage({self._entries})"


class BaggagePropagator:
    """Injects/extracts W3C Baggage headers."""

    def inject(self, baggage: Baggage, carrier: Dict[str, str]) -> Dict[str, str]:
        """Inject baggage into a carrier (e.g. HTTP headers)."""
        if not baggage or len(baggage) == 0:
            return carrier

        parts = []
        for key, value in baggage.entries.items():
            encoded_key = urllib.parse.quote(key, safe="")
            encoded_value = urllib.parse.quote(value, safe="")
            parts.append(f"{encoded_key}={encoded_value}")

        header_value = ", ".join(parts)

        if len(header_value) > _MAX_HEADER_SIZE:
            logger.warning(f"Baggage header exceeds max size ({_MAX_HEADER_SIZE}), truncating")
            header_value = header_value[:_MAX_HEADER_SIZE]

        carrier["baggage"] = header_value
        return carrier

    def extract(self, carrier: Dict[str, str]) -> Baggage:
        """Extract baggage from a carrier (e.g. HTTP headers)."""
        header = carrier.get("baggage", "")
        if not header:
            return Baggage()

        entries: Dict[str, str] = {}
        for member in header.split(","):
            member = member.strip()
            if "=" not in member:
                continue

            # Split on first = only (value may contain =)
            kv = member.split("=", 1)
            key = urllib.parse.unquote(kv[0].strip())
            value = urllib.parse.unquote(kv[1].strip().split(";")[0])  # Strip properties
            entries[key] = value

        return Baggage(entries)


# Module-level convenience
_propagator = BaggagePropagator()


def inject_baggage(baggage: Baggage, headers: Dict[str, str]) -> Dict[str, str]:
    """Inject W3C Baggage into headers."""
    return _propagator.inject(baggage, headers)


def extract_baggage(headers: Dict[str, str]) -> Baggage:
    """Extract W3C Baggage from headers."""
    return _propagator.extract(headers)
