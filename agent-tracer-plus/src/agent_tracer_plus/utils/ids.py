"""ID generation utilities.

Generates globally unique, sortable identifiers for traces, spans, and executions.
Uses time-ordered UUIDs (UUID7-like) for sortability with UUID4 fallback guarantee.
"""

from __future__ import annotations

import os
import struct
import time
import uuid


def _uuid7_like() -> str:
    """Generate a time-ordered UUID similar to UUIDv7.

    Format: 8-char timestamp hex + 24-char random hex = 32 hex chars.
    This gives us chronological sortability while maintaining uniqueness.
    """
    # Millisecond-precision unix timestamp (48 bits)
    timestamp_ms = int(time.time() * 1000)
    ts_bytes = struct.pack(">Q", timestamp_ms)[-6:]  # Last 6 bytes = 48 bits

    # 10 random bytes for uniqueness
    random_bytes = os.urandom(10)

    # Combine: 6 bytes timestamp + 10 bytes random = 16 bytes
    raw = ts_bytes + random_bytes
    return raw.hex()


def generate_trace_id() -> str:
    """Generate a unique trace ID (32 hex characters, W3C compatible).

    Returns a 32-character hex string that is:
    - Time-ordered for sortability
    - Compatible with W3C Trace Context (128-bit trace-id)
    - Globally unique across distributed systems
    """
    return _uuid7_like()


def generate_span_id() -> str:
    """Generate a unique span ID (16 hex characters, W3C compatible).

    Returns a 16-character hex string compatible with W3C Trace Context (64-bit span-id).
    """
    return os.urandom(8).hex()


def generate_execution_id() -> str:
    """Generate a unique execution ID.

    This is a human-friendly ID used to correlate all traces
    from a single logical execution (e.g., one API request).
    Uses UUID4 for maximum uniqueness without time dependency.
    """
    return str(uuid.uuid4())
