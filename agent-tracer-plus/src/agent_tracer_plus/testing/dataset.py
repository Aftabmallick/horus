"""Dataset and Suite abstractions for prompt testing."""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from agent_tracer_plus.testing.evaluators import Evaluator


@dataclass
class EvalTestCase:
    """A single test case in an evaluation suite."""
    name: str
    input_data: Any
    expected_output: Any
    metadata: Dict[str, Any] = field(default_factory=dict)


class EvalSuite:
    """A collection of test cases and evaluators."""

    def __init__(self, name: str, evaluators: Optional[List[Evaluator]] = None) -> None:
        self.name = name
        self.dataset: List[EvalTestCase] = []
        self.evaluators: List[Evaluator] = evaluators or []

    def add_case(
        self, 
        name: str, 
        input_data: Any, 
        expected_output: Any, 
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Add a test case to the suite."""
        self.dataset.append(
            EvalTestCase(
                name=name,
                input_data=input_data,
                expected_output=expected_output,
                metadata=metadata or {}
            )
        )

    @classmethod
    def from_jsonl(cls, name: str, file_path: str | Path, evaluators: Optional[List[Evaluator]] = None) -> "EvalSuite":
        """Load an evaluation suite from a JSONL file."""
        suite = cls(name=name, evaluators=evaluators)
        path = Path(file_path)
        if not path.exists():
            return suite

        with open(path, "r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                if not line.strip():
                    continue
                data = json.loads(line)
                suite.add_case(
                    name=data.get("name", f"case_{i}"),
                    input_data=data.get("input_data"),
                    expected_output=data.get("expected_output"),
                    metadata=data.get("metadata", {})
                )
        return suite
