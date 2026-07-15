"""Golden trace baseline management."""

import json
from pathlib import Path

from agent_tracer_plus.core.models import Span, Trace


class GoldenTrace:
    """Represents a frozen 'golden' trace used as a testing baseline."""

    def __init__(self, trace: Trace, spans: list[Span], name: str = "") -> None:
        self.trace = trace
        self.spans = spans
        self.name = name or trace.trace_id

    def save(self, directory: str | Path) -> None:
        """Save the golden trace to disk."""
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        file_path = directory / f"{self.name}.json"

        data = {
            "trace": self.trace.to_dict(),
            "spans": [s.to_dict() for s in self.spans]
        }
        with open(file_path, "w") as f:
            json.dump(data, f, indent=2)

    @classmethod
    def load(cls, file_path: str | Path) -> "GoldenTrace":
        """Load a golden trace from disk."""
        path = Path(file_path)
        with open(path) as f:
            data = json.load(f)

        trace = Trace.from_dict(data["trace"])
        spans = [Span.from_dict(sd) for sd in data["spans"]]
        return cls(trace=trace, spans=spans, name=path.stem)

    def assert_matches(self, actual_spans: list[Span], strict: bool = False) -> None:
        """Assert that an actual trace execution matches this golden baseline.
        
        Args:
            actual_spans: The spans produced by the replay/test execution.
            strict: If True, requires exact output matching. If False, just checks structure.
        """
        assert len(actual_spans) == len(self.spans), f"Span count mismatch: expected {len(self.spans)}, got {len(actual_spans)}"

        # Sort both chronologically
        expected = sorted(self.spans, key=lambda s: s.started_at)
        actual = sorted(actual_spans, key=lambda s: s.started_at)

        for e_span, a_span in zip(expected, actual):
            assert e_span.name == a_span.name, f"Span name mismatch: expected {e_span.name}, got {a_span.name}"
            assert e_span.span_type == a_span.span_type, f"Span type mismatch for {e_span.name}"

            if strict:
                # Optionally assert inputs/outputs match precisely
                assert e_span.output == a_span.output, f"Output mismatch for span {e_span.name}"
