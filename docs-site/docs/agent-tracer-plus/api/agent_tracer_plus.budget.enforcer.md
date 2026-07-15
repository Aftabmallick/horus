# Module: `agent_tracer_plus.budget.enforcer`

Token and cost budget enforcement.

## Class `BudgetExceededError`
Raised when a trace exceeds its configured budget.

## Class `TokenBudget`
Budget configuration for a trace or agent.

## Class `BudgetEnforcer`
Enforces token and cost limits during a trace's lifecycle.

### `def __init__(self, budget)`
### `def check_budget(self, trace)`
Check the current usage against the budget.

Raises BudgetExceededError if on_exceed == "kill" and limits are crossed.

