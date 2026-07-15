# Module: `agent_tracer_plus.storage.postgresql`

PostgreSQL storage backend for high-throughput production environments.

## Class `PostgreSQLBackend`
Production-ready PostgreSQL storage using asyncpg.

Args:
    dsn: Database connection string (e.g., postgresql://user:pass@localhost:5432/db)

### `def __init__(self, dsn)`
