"""Concurrent evaluation runner for prompt testing suites."""

import asyncio
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from agent_tracer_plus.core.context import get_tracer
from agent_tracer_plus.testing.dataset import EvalSuite, EvalTestCase
from agent_tracer_plus.testing.evaluators import Score
from agent_tracer_plus.utils.logger import get_logger

logger = get_logger("testing.runner")


@dataclass
class EvalResult:
    """The result of evaluating a single test case."""
    test_case: EvalTestCase
    scores: List[Score]
    trace_id: Optional[str] = None
    error: Optional[str] = None


@dataclass
class SuiteResult:
    """The aggregated result of evaluating an entire suite."""
    suite_name: str
    results: List[EvalResult] = field(default_factory=list)

    def average_score(self, evaluator_name: str) -> float:
        """Calculate the average score for a specific evaluator."""
        total = 0.0
        count = 0
        for r in self.results:
            for s in r.scores:
                if s.name == evaluator_name:
                    total += s.value
                    count += 1
        return total / count if count > 0 else 0.0


class AsyncEvalRunner:
    """Runs evaluation suites concurrently."""

    def __init__(self, concurrency: int = 5) -> None:
        self.concurrency = concurrency
        self._semaphore = asyncio.Semaphore(concurrency)

    async def run_suite(
        self, 
        suite: EvalSuite, 
        agent_func: Callable[[Any], Any],
        replay_trace_id: Optional[str] = None
    ) -> SuiteResult:
        """Run the evaluation suite concurrently."""
        suite_result = SuiteResult(suite_name=suite.name)
        
        # Determine if we should inject replay engine
        # (This requires setting up config dynamically or passing it to the tracer context)
        # For simplicity, we assume agent_func handles its own Tracer context, 
        # but we can wrap it if needed.
        
        async def evaluate_case(case: EvalTestCase) -> EvalResult:
            async with self._semaphore:
                scores = []
                trace_id = None
                error = None
                
                try:
                    # Run the agent function
                    # If agent_func is async, await it
                    if asyncio.iscoroutinefunction(agent_func):
                        actual_output = await agent_func(case.input_data)
                    else:
                        # Run sync function in thread pool
                        actual_output = await asyncio.to_thread(agent_func, case.input_data)

                    # Extract trace_id from current context if possible
                    # (Assuming agent_func wrapped itself in TraceContext)
                    from agent_tracer_plus.core.context import get_current_trace
                    current_trace = get_current_trace()
                    if current_trace:
                        trace_id = current_trace.trace_id

                    # Run all evaluators concurrently
                    eval_tasks = [
                        ev.evaluate(case.expected_output, actual_output)
                        for ev in suite.evaluators
                    ]
                    scores = await asyncio.gather(*eval_tasks)
                    
                except Exception as e:
                    error = str(e)
                    logger.error(f"Error evaluating {case.name}: {e}")

                return EvalResult(
                    test_case=case,
                    scores=scores,
                    trace_id=trace_id,
                    error=error
                )

        tasks = [evaluate_case(case) for case in suite.dataset]
        results = await asyncio.gather(*tasks)
        suite_result.results = list(results)
        return suite_result
