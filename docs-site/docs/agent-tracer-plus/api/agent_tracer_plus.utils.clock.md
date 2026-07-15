# Module: `agent_tracer_plus.utils.clock`

High-resolution timing utilities.

## Function `now_utc()`
Return the current UTC datetime with timezone info.

## Function `monotonic_ns()`
Return a monotonic clock value in nanoseconds for duration measurement.

## Function `duration_ms(start_ns, end_ns)`
Calculate duration in milliseconds from nanosecond monotonic timestamps.

Args:
    start_ns: Start time from monotonic_ns().
    end_ns: End time from monotonic_ns(). If None, uses current time.

Returns:
    Duration in milliseconds with microsecond precision.

## Function `timestamp_iso(dt)`
Convert datetime to ISO 8601 string. Defaults to now_utc().

