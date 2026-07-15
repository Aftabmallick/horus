# Module: `agent_tracer_plus.experiments.shadow`

Shadow deployments — run challenger model in background without affecting production.

## Class `ShadowResult`
Result of a shadow deployment comparison.

### `def __init__(self, primary_result, shadow_result, primary_duration_ms, shadow_duration_ms, match)`
### `def to_dict(self)`
## Class `ShadowDeploy`
Run challenger model in the background without affecting production path.

The primary callable always returns the production result. The shadow callable
runs concurrently and its results are logged for comparison but never returned
to the caller.

### `def __init__(self, primary, shadow, comparator)`
### `def get_comparison_stats(self)`
Get statistics from shadow comparisons.

