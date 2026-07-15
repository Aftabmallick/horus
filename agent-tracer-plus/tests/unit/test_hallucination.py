"""Unit tests for the Hallucination Scoring engine."""

import sys
from unittest.mock import AsyncMock, patch, MagicMock
import pytest

from agent_tracer_plus.core.models import Span, SpanType, Trace
from agent_tracer_plus.intelligence.hallucination import (
    detect_hallucination,
    LLMJudgeEngine,
    CrossEncoderEngine,
    HallucinationScore,
    ClaimScore
)

@pytest.mark.asyncio
async def test_llm_judge_hallucination():
    trace = Trace(trace_id="1")
    s1 = Span(name="retrieve", span_type=SpanType.RETRIEVAL, output="The sky is blue and the grass is green.", started_at=1)
    s2 = Span(name="llm", span_type=SpanType.LLM, output="The sky is red. The grass is green.", started_at=2)

    # Mock litellm to return a hallucination report
    mock_response = type("Response", (), {
        "choices": [
            type("Choice", (), {
                "message": type("Message", (), {
                    "content": '{"claims": [{"claim": "The sky is red", "entailed": false, "reason": "contradicts context"}, {"claim": "The grass is green", "entailed": true, "reason": "matches context"}]}'
                })()
            })()
        ]
    })()

    mock_litellm = MagicMock()
    mock_litellm.acompletion = AsyncMock(return_value=mock_response)

    with patch.dict(sys.modules, {"litellm": mock_litellm}):
        scores = await detect_hallucination(trace, [s1, s2], engine=LLMJudgeEngine())
        
        assert len(scores) == 1
        score = scores[0]
        assert score.score == 0.5  # 1 out of 2 claims entailed
        assert len(score.claims) == 2
        assert score.claims[0].entailed is False
        assert score.claims[1].entailed is True


@pytest.mark.asyncio
async def test_cross_encoder_hallucination():
    trace = Trace(trace_id="1")
    s1 = Span(name="retrieve", span_type=SpanType.RETRIEVAL, output="The sky is blue and the grass is green.", started_at=1)
    s2 = Span(name="llm", span_type=SpanType.LLM, output="The sky is red. The grass is green.", started_at=2)

    # Mock sentence_transformers and numpy
    class MockCrossEncoder:
        def __init__(self, *args, **kwargs):
            pass
        def predict(self, pairs):
            import numpy as np
            # Return mocked logits. [Contradiction, Entailment, Neutral]
            # First pair: (context, "The sky is red") -> Contradiction (index 0)
            # Second pair: (context, "The grass is green") -> Entailment (index 1)
            return [
                np.array([5.0, -1.0, -1.0]),  # Argmax = 0 (Contradiction)
                np.array([-1.0, 5.0, -1.0])   # Argmax = 1 (Entailment)
            ]

    mock_st = MagicMock()
    mock_st.CrossEncoder = MockCrossEncoder

    with patch.dict(sys.modules, {"sentence_transformers": mock_st}):
        engine = CrossEncoderEngine()
        scores = await detect_hallucination(trace, [s1, s2], engine=engine)
        
        assert len(scores) == 1
        score = scores[0]
        assert score.score == 0.5
        assert len(score.claims) == 2
        assert score.claims[0].entailed is False
        assert score.claims[1].entailed is True
