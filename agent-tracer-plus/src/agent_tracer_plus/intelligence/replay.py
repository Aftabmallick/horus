"""Time-Travel Replay Engine for Agent Tracer Plus.

The ReplayEngine works by intercepting I/O spans at execution time via the tracer's
`check_replay()` hook. When an auto-instrumented function (LLM, HTTP, Tool) is about
to execute, the tracer calls `should_mock()` which returns the recorded output instead
of making the real call — giving us deterministic replay.

Diverge mode: call `load(diverge_span_id=X)` to replay up to span X with mocked I/O,
then switch to live execution from that point onward (what-if analysis).
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

from agent_tracer_plus.core.models import Span, Trace
from agent_tracer_plus.storage.base import StorageBackend
from agent_tracer_plus.utils.logger import get_logger

logger = get_logger("intelligence.replay")


class ReplayError(Exception):
    """Exception raised during replay when execution diverges unexpectedly."""


class ReplayEngine:
    """Replays a historical trace deterministically.

    This engine integrates with the core tracer. When an auto-instrumented
    function is called (LLM, HTTP, Tool), the tracer asks the ReplayEngine
    if it should be mocked via `check_replay()` → `should_mock()`.

    The engine matches the call against historical spans by type, name, and
    input hash, returns the recorded output, and advances its internal pointer.

    Usage via tracer config::

        import agent_tracer_plus
        agent_tracer_plus.init(
            replay_trace_id="abc-123",
            # optionally: replay_diverge_span_id="step-3"  # live from here
        )

    Usage standalone::

        engine = ReplayEngine(trace_id="abc-123", storage=storage)
        await engine.load()

        # After loading, pass engine to tracer.replay_engine so all
        # subsequent auto-instrumented calls are intercepted.
    """

    # Span types that represent non-deterministic I/O (we mock these)
    _IO_SPAN_TYPES = frozenset({"LLM", "HTTP", "TOOL", "DB", "RETRIEVAL"})

    def __init__(
        self,
        trace_id: str,
        storage: StorageBackend,
        diverge_span_id: Optional[str] = None,
    ) -> None:
        self.trace_id = trace_id
        self.storage = storage
        self.trace: Optional[Trace] = None
        self.spans: List[Span] = []

        self._io_spans: List[Span] = []   # Only I/O spans (mocked in order)
        self._replay_index = 0
        self._diverge_span_id = diverge_span_id
        self.diverged: bool = False
        self._loaded: bool = False

    async def load(self) -> None:
        """Load the trace and its spans from storage."""
        self.trace = await self.storage.get_trace(self.trace_id)
        if not self.trace:
            raise ValueError(f"Trace '{self.trace_id}' not found in storage.")

        all_spans = await self.storage.get_spans(self.trace_id)
        # Sort chronologically by start time
        self.spans = sorted(all_spans, key=lambda s: s.started_at)

        # Filter to I/O spans only — these are the ones we intercept
        self._io_spans = [
            s for s in self.spans
            if s.span_type.value.upper() in self._IO_SPAN_TYPES
        ]

        self._replay_index = 0
        self.diverged = False
        self._loaded = True

        logger.info(
            f"ReplayEngine loaded trace '{self.trace_id}': "
            f"{len(self.spans)} total spans, "
            f"{len(self._io_spans)} I/O spans to mock."
        )

    # ── Core interception logic ───────────────────────────────────────────────

    def should_mock(
        self, span_type: str, name: str, input_payload: Any
    ) -> Tuple[bool, Any]:
        """Called by tracer for every auto-instrumented I/O call.

        Returns:
            (True, recorded_output) to short-circuit the real call.
            (False, None) to allow the real call to proceed (diverge mode).
        """
        if not self._loaded:
            logger.warning("ReplayEngine.should_mock() called before load(). Allowing live execution.")
            return False, None

        if self.diverged:
            return False, None

        if self._replay_index >= len(self._io_spans):
            logger.info(
                f"Replay complete (all {len(self._io_spans)} I/O spans replayed). "
                f"Switching to live execution."
            )
            self.diverged = True
            return False, None

        expected = self._io_spans[self._replay_index]

        # Verify span type matches
        if expected.span_type.value.upper() != span_type.upper():
            logger.warning(
                f"Replay type mismatch at index {self._replay_index}: "
                f"expected {expected.span_type.value}, got {span_type}. "
                f"Diverging to live execution."
            )
            self.diverged = True
            return False, None

        # Verify span name matches
        if expected.name != name:
            logger.warning(
                f"Replay name mismatch at index {self._replay_index}: "
                f"expected '{expected.name}', got '{name}'. "
                f"Diverging to live execution."
            )
            self.diverged = True
            return False, None

        # Verify input hash matches (detect prompt/input drift)
        expected_hash = self._hash_payload(expected.input)
        actual_hash = self._hash_payload(input_payload)
        if expected_hash != actual_hash:
            logger.warning(
                f"Replay input mismatch for '{name}' at index {self._replay_index}. "
                f"Input has changed — diverging to live execution. "
                f"(expected hash: {expected_hash[:8]}, actual: {actual_hash[:8]})"
            )
            self.diverged = True
            return False, None

        # Advance pointer
        self._replay_index += 1

        # Check if this is the diverge point — after returning the mock,
        # all subsequent calls will be live
        if self._diverge_span_id and expected.span_id == self._diverge_span_id:
            logger.info(
                f"Diverge point reached at span '{expected.span_id}' ({name}). "
                f"Returning recorded output, then switching to live execution."
            )
            self.diverged = True

        recorded_output = self._parse_output(expected.output)
        logger.debug(f"[Replay] Mocking {span_type} '{name}' → recorded output")
        return True, recorded_output

    # ── Interactive / step-through API ───────────────────────────────────────

    async def step_through(self) -> AsyncGenerator[Dict[str, Any], None]:
        """Yield each span one-by-one for interactive debugging.

        Usage::
            async for step in engine.step_through():
                print(step["span_name"], step["output"])
        """
        for i, span in enumerate(self.spans):
            is_io = span.span_type.value.upper() in self._IO_SPAN_TYPES
            yield {
                "index": i,
                "span_id": span.span_id,
                "span_name": span.name,
                "span_type": span.span_type.value,
                "is_mocked": is_io,
                "input": span.input,
                "output": span.output,
                "error": span.error,
                "duration_ms": (
                    (span.ended_at - span.started_at) * 1000
                    if span.ended_at and span.started_at
                    else None
                ),
            }

    async def replay(self) -> List[Dict[str, Any]]:
        """Return a structured replay of all spans (for inspection / diff).

        Note: For *actual* re-execution, install this engine into the tracer
        via ``tracer.replay_engine = engine`` before calling your agent function.
        This method returns the historical data for inspection purposes.
        """
        steps = []
        async for step in self.step_through():
            steps.append(step)
        return steps

    def diverge_at(self, span_id: str) -> "ReplayEngine":
        """Configure a diverge point. Returns self for chaining.

        After this span is replayed, all subsequent I/O will be live.
        Use this for what-if analysis: replay up to a specific step, then
        let the agent re-execute with a modified prompt or tool output.
        """
        self._diverge_span_id = span_id
        self.diverged = False  # Reset in case already diverged
        return self

    # ── Summary ──────────────────────────────────────────────────────────────

    def summary(self) -> Dict[str, Any]:
        """Return replay progress summary."""
        return {
            "trace_id": self.trace_id,
            "loaded": self._loaded,
            "diverged": self.diverged,
            "total_spans": len(self.spans),
            "io_spans_total": len(self._io_spans),
            "io_spans_replayed": self._replay_index,
            "io_spans_remaining": max(0, len(self._io_spans) - self._replay_index),
            "diverge_point": self._diverge_span_id,
        }

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _hash_payload(payload: Any) -> str:
        """Create a deterministic hash of an input payload for comparison."""
        if payload is None:
            return hashlib.md5(b"__none__").hexdigest()
        if isinstance(payload, str):
            data = payload
        else:
            try:
                data = json.dumps(payload, sort_keys=True, default=str)
            except Exception:
                data = str(payload)
        return hashlib.md5(data.encode("utf-8")).hexdigest()

    @staticmethod
    def _parse_output(output: Any) -> Any:
        """Attempt to parse stored JSON output back into objects."""
        if isinstance(output, str):
            try:
                return json.loads(output)
            except (json.JSONDecodeError, ValueError):
                return output
        return output
