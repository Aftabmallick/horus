"""Hallucination and Faithfulness scoring engines."""

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from agent_tracer_plus.core.models import Span, SpanType, Trace


@dataclass
class ClaimScore:
    """Evaluation of a single factual claim."""
    claim: str
    entailed: bool
    reason: str


@dataclass
class HallucinationScore:
    """Overall hallucination score for a generated span against context."""
    span_id: str
    score: float  # 0.0 to 1.0 (1.0 = perfectly faithful, 0.0 = completely hallucinated)
    claims: List[ClaimScore] = field(default_factory=list)
    error: Optional[str] = None


class HallucinationEngine(ABC):
    @abstractmethod
    async def score(self, context: str, generation: str, span_id: str) -> HallucinationScore:
        """Score a generation against a context."""
        ...


class LLMJudgeEngine(HallucinationEngine):
    """Uses an LLM to extract claims and verify entailment."""

    def __init__(self, model: str = "gpt-4o", api_key: str = ""):
        self.model = model
        self.api_key = api_key

    async def score(self, context: str, generation: str, span_id: str) -> HallucinationScore:
        try:
            import litellm
        except ImportError:
            return HallucinationScore(span_id, 0.0, error="litellm is required for LLMJudgeEngine")

        system_prompt = """You are a strict faithfulness evaluator.
Given a Context and an Output, you must:
1. Extract distinct factual claims made in the Output.
2. For each claim, check if it is explicitly entailed (supported) by the Context.
3. If it introduces new facts not in the context, it is NOT entailed.

Return JSON in this format:
{
    "claims": [
        {"claim": "string", "entailed": boolean, "reason": "string"}
    ]
}"""
        user_prompt = f"Context:\n{context}\n\nOutput:\n{generation}"

        try:
            response = await litellm.acompletion(
                model=self.model,
                api_key=self.api_key if self.api_key else None,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"}
            )
            
            result_text = response.choices[0].message.content
            if not result_text:
                return HallucinationScore(span_id, 0.0, error="Empty response from LLM")
                
            data = json.loads(result_text)
            claims = []
            entailed_count = 0
            
            for c in data.get("claims", []):
                entailed = bool(c.get("entailed", False))
                if entailed:
                    entailed_count += 1
                claims.append(ClaimScore(
                    claim=c.get("claim", ""),
                    entailed=entailed,
                    reason=c.get("reason", "")
                ))
                
            total = len(claims)
            score = (entailed_count / total) if total > 0 else 1.0
            
            return HallucinationScore(span_id, score, claims=claims)
            
        except Exception as e:
            return HallucinationScore(span_id, 0.0, error=str(e))


class CrossEncoderEngine(HallucinationEngine):
    """Uses a local NLI model (e.g. cross-encoder/nli-deberta-v3-small) to check entailment."""

    def __init__(self, model_name: str = "cross-encoder/nli-deberta-v3-small"):
        self.model_name = model_name
        self._model = None

    def _load_model(self):
        if self._model is None:
            try:
                from sentence_transformers import CrossEncoder
                self._model = CrossEncoder(self.model_name)
            except ImportError:
                raise ImportError("sentence-transformers is required for CrossEncoderEngine")

    async def score(self, context: str, generation: str, span_id: str) -> HallucinationScore:
        try:
            self._load_model()
        except ImportError as e:
            return HallucinationScore(span_id, 0.0, error=str(e))
            
        # NLI models expect (Premise, Hypothesis). 
        # Output is typically [contradiction, entailment, neutral] logits
        # For simplicity, if we chunk the generation into sentences, we can score each sentence.
        # Here we just do a rough sentence split and score.
        sentences = [s.strip() for s in generation.replace("!", ".").replace("?", ".").split(".") if s.strip()]
        if not sentences:
            return HallucinationScore(span_id, 1.0)
            
        pairs = [[context, sent] for sent in sentences]
        try:
            import asyncio
            # Run inference in a threadpool to not block the event loop
            scores = await asyncio.to_thread(self._model.predict, pairs)
            
            claims = []
            entailed_count = 0
            
            for sent, score in zip(sentences, scores):
                # Using a generic heuristic: if entailment logit is highest, or contradiction logit is very low.
                # Deberta-v3 NLI mapping: 0=Contradiction, 1=Entailment, 2=Neutral
                label = score.argmax()
                entailed = bool(label == 1 or label == 2) # Entailment or Neutral is usually acceptable
                if entailed:
                    entailed_count += 1
                claims.append(ClaimScore(
                    claim=sent,
                    entailed=entailed,
                    reason=f"NLI label: {label}"
                ))
                
            total = len(claims)
            final_score = (entailed_count / total) if total > 0 else 1.0
            return HallucinationScore(span_id, final_score, claims=claims)
            
        except Exception as e:
            return HallucinationScore(span_id, 0.0, error=str(e))


async def detect_hallucination(trace: Trace, spans: List[Span], engine: Optional[HallucinationEngine] = None) -> List[HallucinationScore]:
    """Detect hallucination in a trace's LLM outputs compared to preceding retrieval/tool context."""
    if engine is None:
        engine = LLMJudgeEngine()
        
    scores = []
    
    # Simple heuristic: gather all RETRIEVAL and TOOL span outputs prior to the LLM span
    # Alternatively, just gather everything chronological before the LLM span
    spans_sorted = sorted(spans, key=lambda s: s.started_at)
    
    context_accumulator = []
    
    for s in spans_sorted:
        if s.span_type in (SpanType.RETRIEVAL, SpanType.TOOL) and s.output:
            context_accumulator.append(str(s.output))
            
        elif s.span_type == SpanType.LLM and s.output:
            if not context_accumulator:
                # Can't score hallucination if there's no retrieved context
                scores.append(HallucinationScore(s.span_id, 1.0, error="No prior context found to verify against"))
                continue
                
            context_str = "\n".join(context_accumulator)
            generation = str(s.output)
            
            score = await engine.score(context_str, generation, s.span_id)
            scores.append(score)
            
    return scores
