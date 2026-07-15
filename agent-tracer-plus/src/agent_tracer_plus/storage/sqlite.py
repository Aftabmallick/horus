"""SQLite storage backend — zero-config, production-ready for moderate workloads."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiosqlite

from agent_tracer_plus.core.models import Span, Trace
from agent_tracer_plus.storage.base import StorageBackend
from agent_tracer_plus.utils.logger import get_logger

logger = get_logger("storage.sqlite")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS traces (
    trace_id TEXT PRIMARY KEY,
    execution_id TEXT NOT NULL,
    agent_name TEXT DEFAULT '',
    service_name TEXT DEFAULT '',
    session_id TEXT DEFAULT '',
    tenant_id TEXT DEFAULT '',
    started_at TEXT NOT NULL,
    ended_at TEXT,
    duration_ms REAL DEFAULT 0,
    status TEXT DEFAULT 'RUNNING',
    metadata TEXT DEFAULT '{}',
    tags TEXT DEFAULT '[]',
    total_tokens INTEGER DEFAULT 0,
    total_cost REAL DEFAULT 0,
    span_count INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_traces_started_at ON traces(started_at);
CREATE INDEX IF NOT EXISTS idx_traces_status ON traces(status);
CREATE INDEX IF NOT EXISTS idx_traces_agent_name ON traces(agent_name);
CREATE INDEX IF NOT EXISTS idx_traces_tenant_id ON traces(tenant_id);
CREATE INDEX IF NOT EXISTS idx_traces_execution_id ON traces(execution_id);

CREATE TABLE IF NOT EXISTS spans (
    span_id TEXT PRIMARY KEY,
    trace_id TEXT NOT NULL,
    parent_span_id TEXT,
    name TEXT NOT NULL,
    span_type TEXT DEFAULT 'CUSTOM',
    started_at TEXT NOT NULL,
    ended_at TEXT,
    duration_ms REAL DEFAULT 0,
    status TEXT DEFAULT 'RUNNING',
    input TEXT,
    output TEXT,
    error TEXT,
    attributes TEXT DEFAULT '{}',
    events TEXT DEFAULT '[]',
    links TEXT DEFAULT '[]',
    token_usage TEXT,
    cost_info TEXT,
    service_name TEXT DEFAULT '',
    FOREIGN KEY (trace_id) REFERENCES traces(trace_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_spans_trace_id ON spans(trace_id);
CREATE INDEX IF NOT EXISTS idx_spans_name ON spans(name);
CREATE INDEX IF NOT EXISTS idx_spans_span_type ON spans(span_type);
CREATE INDEX IF NOT EXISTS idx_spans_started_at ON spans(started_at);
"""


class SQLiteBackend(StorageBackend):
    """SQLite-based storage using aiosqlite for async I/O.

    Args:
        db_path: Path to the SQLite database file. Created if it doesn't exist.
    """

    def __init__(self, db_path: str = "./agent_traces.db") -> None:
        self._db_path = str(Path(db_path).resolve())
        self._db: Optional[aiosqlite.Connection] = None
        self._initialized = False

    async def _ensure_initialized(self) -> aiosqlite.Connection:
        """Lazily initialize the database connection and schema."""
        if self._db is None or not self._initialized:
            self._db = await aiosqlite.connect(self._db_path)
            await self._db.execute("PRAGMA journal_mode=WAL")
            await self._db.execute("PRAGMA foreign_keys=ON")
            await self._db.executescript(_SCHEMA)
            await self._db.commit()
            self._initialized = True
            logger.debug(f"SQLite backend initialized at {self._db_path}")
        return self._db

    async def save_trace(self, trace: Trace) -> None:
        db = await self._ensure_initialized()
        data = trace.to_dict()
        await db.execute(
            """INSERT OR REPLACE INTO traces
            (trace_id, execution_id, agent_name, service_name, session_id, tenant_id,
             started_at, ended_at, duration_ms, status, metadata, tags,
             total_tokens, total_cost, span_count, error_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                data["trace_id"],
                data["execution_id"],
                data["agent_name"],
                data["service_name"],
                data["session_id"],
                data["tenant_id"],
                data["started_at"],
                data["ended_at"],
                data["duration_ms"],
                data["status"],
                json.dumps(data["metadata"]),
                json.dumps(data["tags"]),
                data["total_tokens"],
                data["total_cost"],
                data["span_count"],
                data["error_count"],
            ),
        )
        await db.commit()

    async def save_span(self, span: Span) -> None:
        db = await self._ensure_initialized()
        data = span.to_dict()
        await db.execute(
            """INSERT OR REPLACE INTO spans
            (span_id, trace_id, parent_span_id, name, span_type,
             started_at, ended_at, duration_ms, status,
             input, output, error, attributes, events, links,
             token_usage, cost_info, service_name)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                data["span_id"],
                data["trace_id"],
                data["parent_span_id"],
                data["name"],
                data["span_type"],
                data["started_at"],
                data["ended_at"],
                data["duration_ms"],
                data["status"],
                json.dumps(data.get("input")),
                json.dumps(data.get("output")),
                json.dumps(data.get("error")),
                json.dumps(data.get("attributes", {})),
                json.dumps(data.get("events", [])),
                json.dumps(data.get("links", [])),
                json.dumps(data.get("token_usage")),
                json.dumps(data.get("cost_info")),
                data.get("service_name", ""),
            ),
        )
        await db.commit()

    async def save_spans_batch(self, spans: List[Span]) -> None:
        db = await self._ensure_initialized()
        rows = []
        for span in spans:
            data = span.to_dict()
            rows.append((
                data["span_id"], data["trace_id"], data["parent_span_id"],
                data["name"], data["span_type"], data["started_at"],
                data["ended_at"], data["duration_ms"], data["status"],
                json.dumps(data.get("input")), json.dumps(data.get("output")),
                json.dumps(data.get("error")), json.dumps(data.get("attributes", {})),
                json.dumps(data.get("events", [])), json.dumps(data.get("links", [])),
                json.dumps(data.get("token_usage")), json.dumps(data.get("cost_info")),
                data.get("service_name", ""),
            ))
        await db.executemany(
            """INSERT OR REPLACE INTO spans
            (span_id, trace_id, parent_span_id, name, span_type,
             started_at, ended_at, duration_ms, status,
             input, output, error, attributes, events, links,
             token_usage, cost_info, service_name)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            rows,
        )
        await db.commit()

    async def get_trace(self, trace_id: str) -> Optional[Trace]:
        db = await self._ensure_initialized()
        async with db.execute("SELECT * FROM traces WHERE trace_id = ?", (trace_id,)) as cursor:
            row = await cursor.fetchone()
            if row is None:
                return None
            columns = [desc[0] for desc in cursor.description]
            data = dict(zip(columns, row))
            trace = Trace(trace_id=data["trace_id"])
            trace.execution_id = data.get("execution_id", "")
            trace.agent_name = data.get("agent_name", "")
            trace.service_name = data.get("service_name", "")
            trace.duration_ms = data.get("duration_ms", 0.0)
            trace.total_tokens = data.get("total_tokens", 0)
            trace.total_cost = data.get("total_cost", 0.0)
            return trace

    async def get_spans(self, trace_id: str) -> List[Span]:
        db = await self._ensure_initialized()
        async with db.execute(
            "SELECT * FROM spans WHERE trace_id = ? ORDER BY started_at", (trace_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            spans = []
            for row in rows:
                data = dict(zip(columns, row))
                span = Span(name=data.get("name", ""), span_id=data.get("span_id", ""))
                span.trace_id = data.get("trace_id", "")
                span.parent_span_id = data.get("parent_span_id")
                span.duration_ms = data.get("duration_ms", 0.0)
                spans.append(span)
            return spans

    async def query_traces(
        self,
        filters: Dict[str, Any] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        db = await self._ensure_initialized()
        query = "SELECT * FROM traces"
        params: list[Any] = []

        # Allowlist of valid column names to prevent SQL injection
        _VALID_COLUMNS = frozenset({
            "trace_id", "execution_id", "agent_name", "service_name",
            "session_id", "tenant_id", "started_at", "ended_at",
            "duration_ms", "status", "total_tokens", "total_cost",
            "span_count", "error_count",
        })

        if filters:
            conditions = []
            for key, value in filters.items():
                if key not in _VALID_COLUMNS:
                    raise ValueError(
                        f"Invalid filter column '{key}'. "
                        f"Allowed columns: {sorted(_VALID_COLUMNS)}"
                    )
                conditions.append(f"{key} = ?")
                params.append(value)
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY started_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        async with db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in rows]


    async def delete_traces(self, before: datetime) -> int:
        db = await self._ensure_initialized()
        before_str = before.isoformat()
        cursor = await db.execute(
            "DELETE FROM traces WHERE started_at < ?", (before_str,)
        )
        await db.commit()
        return cursor.rowcount or 0

    async def flush(self) -> None:
        if self._db:
            await self._db.commit()

    async def close(self) -> None:
        if self._db:
            await self._db.close()
            self._db = None
            self._initialized = False

    async def health_check(self) -> bool:
        try:
            db = await self._ensure_initialized()
            async with db.execute("SELECT 1") as cursor:
                await cursor.fetchone()
            return True
        except Exception:
            return False
