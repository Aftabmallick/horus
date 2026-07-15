# Module: `agent_tracer_plus.processing.retention`

Data retention TTL enforcement worker.

Automatically deletes traces older than configured TTL policies.
Can run as a background asyncio task or be triggered manually.

Usage::

    from agent_tracer_plus.processing.retention import RetentionEnforcer
    from agent_tracer_plus.processing.retention import RetentionPolicy

    policy = RetentionPolicy(
        default_ttl_days=90,
        error_ttl_days=365,
        debug_ttl_days=7,
    )
    enforcer = RetentionEnforcer(storage=backend, policy=policy)

    # Run once
    await enforcer.run_once()

    # Run as a background task (every 24h)
    task = enforcer.start_background_worker(interval_hours=24)

## Class `RetentionPolicy`
Defines TTL (time-to-live) rules per trace category.

Args:
    default_ttl_days: Default retention for all traces.
    error_ttl_days: Retention for traces with status=ERROR (longer — for debugging).
    debug_ttl_days: Retention for traces tagged as debug (shorter — reduce storage).
    custom_rules: Dict of &#123;tag: ttl_days&#125; for custom categories.

### `def cutoff_for(self, category)`
Return the cutoff datetime for a given category.

## Class `RetentionEnforcer`
Enforces data retention TTL policies against a storage backend.

Args:
    storage: A StorageBackend instance that implements delete_traces(before).
    policy: A RetentionPolicy specifying TTL rules.
    dry_run: If True, logs what would be deleted without actually deleting.

### `def __init__(self, storage, policy, dry_run)`
### `def start_background_worker(self, interval_hours)`
Start retention enforcement as a recurring background asyncio task.

Args:
    interval_hours: How often to run (default: every 24 hours).

Returns:
    The asyncio.Task. Cancel it to stop the worker.

### `def stop_background_worker(self)`
Cancel the background worker task.

