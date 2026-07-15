"""Trace test suite management."""

from pathlib import Path
from typing import List

from agent_tracer_plus.testing.golden import GoldenTrace


class TraceTestSuite:
    """A collection of golden traces that serve as a regression suite."""

    def __init__(self, directory: str | Path) -> None:
        self.directory = Path(directory)
        self.golden_traces: List[GoldenTrace] = []
        self._load_all()

    def _load_all(self) -> None:
        """Load all golden traces from the directory."""
        if not self.directory.exists():
            return

        for file_path in self.directory.glob("*.json"):
            try:
                golden = GoldenTrace.load(file_path)
                self.golden_traces.append(golden)
            except Exception as e:
                import logging
                logging.warning(f"Failed to load golden trace {file_path}: {e}")

    @classmethod
    def from_production(cls, storage_backend, filter_args: dict = None, sample_size: int = 10) -> "TraceTestSuite":
        """Draft method for pulling traces from production into a local suite."""
        raise NotImplementedError("Fetching directly from production storage not implemented yet.")
