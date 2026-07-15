from unittest.mock import MagicMock, patch

import pytest

from agent_tracer_plus.search.embeddings import EmbeddingEngine


@pytest.mark.asyncio
async def test_embedding_engine():
    with patch("agent_tracer_plus.search.embeddings._sentence_transformers") as mock_st:
        mock_model = MagicMock()
        mock_array = MagicMock()
        mock_array.tolist.return_value = [[0.1, 0.2, 0.3]]
        mock_model.encode.return_value = mock_array
        mock_st.SentenceTransformer.return_value = mock_model

        engine = EmbeddingEngine()
        engine._load_dependency = MagicMock()

        res = await engine.embed(["test input"])
        assert len(res) == 1
        assert res[0] == [0.1, 0.2, 0.3]

    # Test empty list
    empty_res = await engine.embed([])
    assert empty_res == []
