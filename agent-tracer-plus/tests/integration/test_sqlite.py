import os

import pytest

from agent_tracer_plus.core.models import Span, Trace
from agent_tracer_plus.storage.sqlite import SQLiteBackend


@pytest.mark.asyncio
async def test_sqlite_backend():
    db_path = "test_traces.db"
    if os.path.exists(db_path):
        os.remove(db_path)

    storage = SQLiteBackend(db_path)

    trace = Trace(agent_name="DBAgent", trace_id="trace_123")
    trace.finish()

    span = Span(name="DBSpan", trace_id="trace_123", span_id="span_456")
    span.finish()

    await storage.save_trace(trace)
    await storage.save_span(span)

    retrieved = await storage.get_trace("trace_123")
    assert retrieved is not None
    assert retrieved.agent_name == "DBAgent"

    spans = await storage.get_spans("trace_123")
    assert len(spans) == 1
    assert spans[0].name == "DBSpan"

    await storage.close()
    os.remove(db_path)
