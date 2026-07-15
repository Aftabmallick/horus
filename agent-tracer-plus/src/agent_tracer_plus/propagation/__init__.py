"""Distributed tracing propagation — W3C, B3, and Baggage."""

from agent_tracer_plus.propagation.b3 import extract_b3, inject_b3
from agent_tracer_plus.propagation.baggage import Baggage, extract_baggage, inject_baggage
from agent_tracer_plus.propagation.w3c import extract_context, inject_context

__all__ = [
    "inject_context", "extract_context",
    "inject_b3", "extract_b3",
    "inject_baggage", "extract_baggage", "Baggage",
]
