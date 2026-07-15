# Module: `agent_tracer_plus.storage.resilience`

Circuit breaker for storage backend resilience.

Implements the standard CLOSED → OPEN → HALF_OPEN state machine
to prevent cascading failures when a storage backend is unavailable.

Usage::

    from agent_tracer_plus.storage.resilience import CircuitBreaker

    breaker = CircuitBreaker(
        failure_threshold=5,
        recovery_timeout=30.0,
        name="clickhouse",
    )

    async def save():
        async with breaker:
            await real_backend.save_trace(trace)

## Class `CircuitState`
## Class `CircuitBreakerOpenError`
Raised when a request is rejected because the circuit is OPEN.

## Class `CircuitBreaker`
Async circuit breaker for storage backend calls.

Args:
    failure_threshold: Number of consecutive failures before opening circuit.
    recovery_timeout: Seconds to wait before attempting a recovery probe (HALF_OPEN).
    success_threshold: Consecutive successes in HALF_OPEN to return to CLOSED.
    name: Human-readable name for logging.

### `def __init__(self, failure_threshold, recovery_timeout, success_threshold, name)`
### `def state(self)`
### `def is_closed(self)`
### `def _should_attempt_reset(self)`
Check if enough time has passed to attempt a recovery probe.

### `def reset(self)`
Manually reset the circuit to CLOSED state (for testing/admin use).

### `def stats(self)`
Return current circuit breaker statistics.

