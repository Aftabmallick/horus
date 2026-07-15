from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from agent_tracer_plus.core.models import Span, Trace
from agent_tracer_plus.storage.postgresql import PostgreSQLBackend


@pytest.mark.asyncio
@patch("asyncpg.create_pool", new_callable=AsyncMock)
async def test_postgresql_save_trace(mock_create_pool):
    # Setup mocks
    from unittest.mock import MagicMock
    mock_pool = MagicMock()
    mock_create_pool.return_value = mock_pool
    mock_conn = AsyncMock()
    mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

    # Initialize backend
    backend = PostgreSQLBackend("postgresql://fake:pass@localhost/db")

    trace = Trace(trace_id="t1", agent_name="AgentA")
    trace.started_at = datetime.now(timezone.utc)

    # Act
    await backend.save_trace(trace)

    # Assert
    mock_create_pool.assert_called_once_with("postgresql://fake:pass@localhost/db", min_size=1, max_size=10)
    mock_conn.execute.assert_called()
    args = mock_conn.execute.call_args[0]

    # First argument is the query, the rest are params
    assert "INSERT INTO traces" in args[0]
    assert args[1] == "t1" # trace_id
    assert args[3] == "AgentA" # agent_name

@pytest.mark.asyncio
@patch("asyncpg.create_pool", new_callable=AsyncMock)
async def test_postgresql_save_spans(mock_create_pool):
    from unittest.mock import MagicMock
    mock_pool = MagicMock()
    mock_create_pool.return_value = mock_pool
    mock_conn = AsyncMock()
    mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

    backend = PostgreSQLBackend("postgresql://fake:pass@localhost/db")

    span = Span(name="step_1", trace_id="t1")
    span.started_at = datetime.now(timezone.utc)

    await backend.save_spans_batch([span])

    mock_conn.executemany.assert_called_once()
    args = mock_conn.executemany.call_args[0]
    assert "INSERT INTO spans" in args[0]

    records = args[1]
    assert len(records) == 1
    assert records[0][0] == span.span_id
    assert records[0][3] == "step_1" # name
