"""ClickHouse storage backend for Agent Tracer Plus."""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from agent_tracer_plus.core.models import Span, Trace
from agent_tracer_plus.storage.base import StorageBackend

logger = logging.getLogger(__name__)

try:
    import clickhouse_connect
    HAS_CLICKHOUSE = True
except ImportError:
    HAS_CLICKHOUSE = False


class ClickHouseStorage(StorageBackend):
    """Stores traces and spans in ClickHouse."""

    def __init__(self, host: str = "localhost", port: int = 8123,
                 username: str = "default", password: str = "",
                 database: str = "agent_tracer",
                 ttl_days: int = 30):
        if not HAS_CLICKHOUSE:
            raise ImportError(
                "clickhouse-connect is required for ClickHouse storage. "
                "Install it with: pip install clickhouse-connect"
            )

        self.database = database
        self.client = clickhouse_connect.get_client(
            host=host, port=port, username=username, password=password
        )
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database and tables."""
        self.client.command(f"CREATE DATABASE IF NOT EXISTS {self.database}")

        self.ttl_days = getattr(self, "ttl_days", 30)

        # We store traces as JSON strings to maintain flexibility
        # while using ClickHouse's fast JSON extraction functions
        self.client.command(f"""
            CREATE TABLE IF NOT EXISTS {self.database}.traces (
                trace_id String,
                start_time DateTime64(6),
                data String,
                tenant_id String DEFAULT ''
            ) ENGINE = MergeTree()
            ORDER BY (start_time, trace_id)
            TTL start_time + INTERVAL {self.ttl_days} DAY
        """)

        self.client.command(f"""
            CREATE TABLE IF NOT EXISTS {self.database}.spans (
                trace_id String,
                span_id String,
                start_time DateTime64(6),
                span_type String,
                data String
            ) ENGINE = MergeTree()
            ORDER BY (trace_id, start_time)
            TTL start_time + INTERVAL {self.ttl_days} DAY
        """)

    async def save_trace(self, trace: Trace) -> None:
        """Persist a completed trace."""
        trace_dict = trace.to_dict()
        start_time_dt = datetime.fromisoformat(trace_dict["start_time"].replace("Z", "+00:00"))

        self.client.insert(
            f'{self.database}.traces',
            [[
                trace.trace_id,
                start_time_dt,
                json.dumps(trace_dict),
                trace.tenant_id or ""
            ]],
            column_names=['trace_id', 'start_time', 'data', 'tenant_id']
        )

    async def save_span(self, span: Span) -> None:
        """Persist a completed span."""
        span_dict = span.to_dict()
        start_time_dt = datetime.fromisoformat(span_dict["start_time"].replace("Z", "+00:00"))

        self.client.insert(
            f'{self.database}.spans',
            [[
                span.trace_id,
                span.span_id,
                start_time_dt,
                span.span_type,
                json.dumps(span_dict)
            ]],
            column_names=['trace_id', 'span_id', 'start_time', 'span_type', 'data']
        )

    async def save_spans_batch(self, spans: List[Span]) -> None:
        """Persist a batch of spans efficiently."""
        if not spans:
            return

        rows = []
        for span in spans:
            span_dict = span.to_dict()
            start_time_dt = datetime.fromisoformat(span_dict["start_time"].replace("Z", "+00:00"))
            rows.append([
                span.trace_id,
                span.span_id,
                start_time_dt,
                span.span_type,
                json.dumps(span_dict)
            ])

        self.client.insert(
            f'{self.database}.spans',
            rows,
            column_names=['trace_id', 'span_id', 'start_time', 'span_type', 'data']
        )

    async def get_trace(self, trace_id: str) -> Optional[Trace]:
        """Retrieve a trace by ID."""
        result = self.client.query(
            f"SELECT data FROM {self.database}.traces WHERE trace_id = {{trace_id:String}} LIMIT 1",
            parameters={"trace_id": trace_id}
        )
        if result.result_rows:
            return Trace.from_dict(json.loads(result.result_rows[0][0]))
        return None

    async def get_spans(self, trace_id: str) -> List[Span]:
        """Retrieve all spans for a trace."""
        result = self.client.query(
            f"SELECT data FROM {self.database}.spans WHERE trace_id = {{trace_id:String}} ORDER BY start_time",
            parameters={"trace_id": trace_id}
        )
        spans = []
        for row in result.result_rows:
            spans.append(Span.from_dict(json.loads(row[0])))
        return spans

    async def query_traces(
        self,
        filters: Dict[str, Any] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Query traces. Complex filtering should be optimized via ClickHouse JSON functions."""
        # This is a simplified query; production would map filters to JSONExtract functions
        query = f"SELECT data FROM {self.database}.traces"
        parameters = {}

        conditions = []
        if filters:
            if "tenant_id" in filters:
                conditions.append("tenant_id = {tenant_id:String}")
                parameters["tenant_id"] = filters['tenant_id']

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += f" ORDER BY start_time DESC LIMIT {limit} OFFSET {offset}"

        result = self.client.query(query, parameters=parameters)
        traces = []
        for row in result.result_rows:
            traces.append(json.loads(row[0]))
        return traces

    async def delete_traces(self, before: datetime) -> int:
        """Delete traces older than the given datetime.
        Note: ALTER TABLE DELETE is a heavy mutation in ClickHouse."""

        time_str = before.strftime('%Y-%m-%d %H:%M:%S')

        # Get count to return
        count_query = f"SELECT count() FROM {self.database}.traces WHERE start_time < '{time_str}'"
        count = self.client.query(count_query).result_rows[0][0]

        if count > 0:
            self.client.command(f"ALTER TABLE {self.database}.traces DELETE WHERE start_time < '{time_str}'")
            self.client.command(f"ALTER TABLE {self.database}.spans DELETE WHERE start_time < '{time_str}'")

        return int(count)

    async def flush(self) -> None:
        """Flush handled by clickhouse-connect."""
        pass

    async def close(self) -> None:
        """Close the ClickHouse client."""
        if hasattr(self, 'client'):
            self.client.close()

    async def health_check(self) -> bool:
        """Check if ClickHouse is reachable."""
        try:
            return self.client.ping()
        except Exception as e:
            logger.error(f"ClickHouse health check failed: {e}")
            return False
