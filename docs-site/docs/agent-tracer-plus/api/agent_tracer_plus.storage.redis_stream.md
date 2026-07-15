# Module: `agent_tracer_plus.storage.redis_stream`

Redis Stream storage backend for Agent Tracer Plus.

## Class `RedisStreamStorage`
Stores traces and spans in Redis Streams for fast ingestion.

### `def __init__(self, url, stream_prefix, max_len)`
