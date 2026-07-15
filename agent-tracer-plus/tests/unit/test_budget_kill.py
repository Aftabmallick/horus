import pytest

from agent_tracer_plus.budget.enforcer import BudgetExceededError
from agent_tracer_plus.core.config import TracerConfig
from agent_tracer_plus.core.models import Trace
from agent_tracer_plus.core.tracer import AgentTracerPlus

def test_tracer_enforces_budget_kill():
    # Configure tracer with a strict budget
    config = TracerConfig(
        budget={"max_tokens_per_trace": 100, "on_exceed": "kill"},
        enabled=True
    )
    tracer = AgentTracerPlus(config)

    # Valid trace
    valid_trace = Trace(trace_id="t_valid", total_tokens=50)
    tracer._enqueue_trace(valid_trace)  # Should not raise

    # Invalid trace - exceeds token budget
    invalid_trace = Trace(trace_id="t_invalid", total_tokens=150)
    with pytest.raises(BudgetExceededError, match="Token limit exceeded"):
        tracer._enqueue_trace(invalid_trace)
