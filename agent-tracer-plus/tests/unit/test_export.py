import json
import os
from unittest.mock import AsyncMock, patch

import pytest

from agent_tracer_plus.cli.export import export_traces_async


@pytest.fixture
def temp_output(tmp_path):
    return os.path.join(tmp_path, "output")

@pytest.mark.asyncio
async def test_export_jsonl(temp_output):
    with patch("agent_tracer_plus.core.tracer.AgentTracerPlus._storage_from_uri") as mock_storage_factory:
        mock_storage = AsyncMock()
        mock_storage.query_traces.side_effect = [
            [{"trace_id": "1", "status": "success"}, {"trace_id": "2", "status": "error"}],
            [] # end
        ]
        mock_storage_factory.return_value = mock_storage

        await export_traces_async("sqlite://./test.db", "jsonl", temp_output, limit=10)

        assert os.path.exists(temp_output)
        with open(temp_output) as f:
            lines = f.readlines()
            assert len(lines) == 2
            assert json.loads(lines[0])["trace_id"] == "1"

@pytest.mark.asyncio
async def test_export_csv(temp_output):
    with patch("agent_tracer_plus.core.tracer.AgentTracerPlus._storage_from_uri") as mock_storage_factory:
        mock_storage = AsyncMock()
        mock_storage.query_traces.side_effect = [
            [{"trace_id": "1", "status": "success"}],
            []
        ]
        mock_storage_factory.return_value = mock_storage

        await export_traces_async("sqlite://./test.db", "csv", temp_output, limit=10)

        with open(temp_output) as f:
            content = f.read()
            assert "trace_id,status" in content
            assert "1,success" in content
