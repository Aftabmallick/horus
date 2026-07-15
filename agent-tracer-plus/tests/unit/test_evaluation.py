"""Unit tests for the evaluation framework."""

import pytest
from agent_tracer_plus.testing.dataset import EvalSuite, EvalTestCase
from agent_tracer_plus.testing.evaluators import ExactMatchEvaluator, ContainsEvaluator
from agent_tracer_plus.testing.runner import AsyncEvalRunner


async def dummy_agent(input_data: str) -> str:
    """A dummy agent function for testing."""
    if input_data == "hello":
        return "world"
    elif input_data == "foo":
        return "bar"
    return "unknown"


@pytest.mark.asyncio
async def test_eval_suite_and_runner():
    # 1. Create evaluators
    evaluators = [
        ExactMatchEvaluator(name="exact"),
        ContainsEvaluator(name="contains")
    ]
    
    # 2. Create a suite
    suite = EvalSuite(name="test_suite", evaluators=evaluators)
    suite.add_case(name="case_hello", input_data="hello", expected_output="world")
    suite.add_case(name="case_foo", input_data="foo", expected_output="baz")  # Deliberately expect 'baz' to test failure
    
    # 3. Run the evaluation concurrently
    runner = AsyncEvalRunner(concurrency=2)
    result = await runner.run_suite(suite, dummy_agent)
    
    assert result.suite_name == "test_suite"
    assert len(result.results) == 2
    
    # case_hello should score 1.0 on both exact and contains
    hello_result = next(r for r in result.results if r.test_case.name == "case_hello")
    assert hello_result.scores[0].name == "exact"
    assert hello_result.scores[0].value == 1.0
    assert hello_result.scores[1].name == "contains"
    assert hello_result.scores[1].value == 1.0
    
    # case_foo should score 0.0 on both (agent returns 'bar', expected 'baz')
    foo_result = next(r for r in result.results if r.test_case.name == "case_foo")
    assert foo_result.scores[0].name == "exact"
    assert foo_result.scores[0].value == 0.0
    assert foo_result.scores[1].name == "contains"
    assert foo_result.scores[1].value == 0.0
    
    # Check average scores
    avg_exact = result.average_score("exact")
    assert avg_exact == 0.5  # (1.0 + 0.0) / 2
    
    avg_contains = result.average_score("contains")
    assert avg_contains == 0.5
