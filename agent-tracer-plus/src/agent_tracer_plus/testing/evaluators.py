"""Evaluation functions and protocols for scoring traces."""

import json
import re
from dataclasses import dataclass
from typing import Any, Optional, Protocol, runtime_checkable


@dataclass
class Score:
    """Represents a score from an evaluator."""
    name: str
    value: float  # 0.0 to 1.0
    reasoning: Optional[str] = None


@runtime_checkable
class Evaluator(Protocol):
    """Protocol for all evaluators."""
    
    async def evaluate(self, expected: Any, actual: Any, **kwargs: Any) -> Score:
        """Evaluate the actual output against the expected baseline."""
        ...


class ExactMatchEvaluator:
    """Evaluates if the actual string exactly matches the expected string."""
    
    def __init__(self, name: str = "exact_match") -> None:
        self.name = name

    async def evaluate(self, expected: Any, actual: Any, **kwargs: Any) -> Score:
        is_match = str(expected) == str(actual)
        return Score(
            name=self.name,
            value=1.0 if is_match else 0.0,
            reasoning="Exact match" if is_match else f"Expected '{expected}', got '{actual}'"
        )


class ContainsEvaluator:
    """Evaluates if the actual string contains the expected substring."""
    
    def __init__(self, name: str = "contains") -> None:
        self.name = name

    async def evaluate(self, expected: Any, actual: Any, **kwargs: Any) -> Score:
        actual_str = str(actual)
        expected_str = str(expected)
        is_match = expected_str in actual_str
        return Score(
            name=self.name,
            value=1.0 if is_match else 0.0,
            reasoning=f"Found '{expected_str}'" if is_match else f"Missing '{expected_str}'"
        )


class RegexEvaluator:
    """Evaluates if the actual string matches a specific regex pattern (expected is ignored or used as pattern)."""
    
    def __init__(self, pattern: str, name: str = "regex_match") -> None:
        self.name = name
        self.pattern = re.compile(pattern)

    async def evaluate(self, expected: Any, actual: Any, **kwargs: Any) -> Score:
        is_match = bool(self.pattern.search(str(actual)))
        return Score(
            name=self.name,
            value=1.0 if is_match else 0.0,
            reasoning=f"Matched pattern {self.pattern.pattern}" if is_match else "Did not match pattern"
        )


class JSONSchemaEvaluator:
    """Evaluates if the actual output is valid JSON (and optionally matches a schema)."""
    
    def __init__(self, name: str = "valid_json") -> None:
        self.name = name

    async def evaluate(self, expected: Any, actual: Any, **kwargs: Any) -> Score:
        try:
            json.loads(str(actual))
            return Score(name=self.name, value=1.0, reasoning="Valid JSON")
        except json.JSONDecodeError as e:
            return Score(name=self.name, value=0.0, reasoning=f"Invalid JSON: {e}")
