import pytest

from agent_tracer_plus.budget.enforcer import BudgetEnforcer, BudgetExceededError, TokenBudget
from agent_tracer_plus.core.models import Trace


def test_budget_enforcer_kill():
    budget = TokenBudget(max_tokens_per_trace=1000, max_cost_per_trace=0.05, on_exceed="kill")
    enforcer = BudgetEnforcer(budget)

    trace = Trace(trace_id="t1", total_tokens=500, total_cost=0.01)
    enforcer.check_budget(trace)  # Should pass

    trace.total_tokens = 1200
    with pytest.raises(BudgetExceededError, match="Token limit exceeded"):
        enforcer.check_budget(trace)

    trace.total_tokens = 500
    trace.total_cost = 0.06
    with pytest.raises(BudgetExceededError, match="Cost limit exceeded"):
        enforcer.check_budget(trace)

def test_budget_enforcer_alert_log():
    budget = TokenBudget(max_tokens_per_trace=1000, on_exceed="log")
    enforcer = BudgetEnforcer(budget)

    trace = Trace(trace_id="t2", total_tokens=1500)
    enforcer.check_budget(trace)  # Should not raise exception
