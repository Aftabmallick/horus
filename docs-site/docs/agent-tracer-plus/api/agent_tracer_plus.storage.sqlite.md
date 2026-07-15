# Module: `agent_tracer_plus.storage.sqlite`

SQLite storage backend — zero-config, production-ready for moderate workloads.

## Class `SQLiteBackend`
SQLite-based storage using aiosqlite for async I/O.

Args:
    db_path: Path to the SQLite database file. Created if it doesn't exist.

### `def __init__(self, db_path)`
