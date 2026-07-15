"""Semantic search over traces using embedding similarity."""

from __future__ import annotations

import logging
import asyncio
import math
from collections import defaultdict
from typing import Any, Dict, List, Optional

from agent_tracer_plus.core.context import get_tracer
from agent_tracer_plus.search.embeddings import EmbeddingEngine

logger = logging.getLogger(__name__)


class SemanticSearcher:
    """Natural language search across traces using hybrid vector + BM25 similarity (RRF)."""

    def __init__(self, embedding_engine: Optional[EmbeddingEngine] = None):
        self._engine = embedding_engine
        self._index: List[Dict[str, Any]] = []  # In-memory index
        
        # BM25 sparse search state
        self._bm25_doc_len: Dict[str, int] = {}
        self._bm25_doc_freqs: List[Dict[str, int]] = []
        self._bm25_doc_freq: Dict[str, int] = defaultdict(int)
        self._avgdl = 0.0
        self._n_docs = 0
        
        # Background indexing task
        self._indexing_task: Optional[asyncio.Task] = None

    def _get_engine(self) -> EmbeddingEngine:
        if self._engine is None:
            self._engine = EmbeddingEngine()
        return self._engine

    async def _build_text(self, trace_dict: Dict[str, Any], spans: list) -> str:
        """Build a searchable text representation of a trace."""
        parts = [
            f"agent:{trace_dict.get('agent_name', '')}",
            f"status:{trace_dict.get('status', '')}",
            f"service:{trace_dict.get('service_name', '')}",
        ]
        for s in spans:
            parts.append(f"span:{s.name}")
            if s.input:
                parts.append(str(s.input)[:500])
            if s.output:
                parts.append(str(s.output)[:500])
            if s.error:
                parts.append(f"error:{s.error.get('type', '')}:{s.error.get('message', '')}")
                parts.append(f"error:{s.error.get('type', '')}:{s.error.get('message', '')}")
        return " ".join(parts)

    def _tokenize(self, text: str) -> List[str]:
        return text.lower().split()

    def _update_bm25_index(self, texts: List[str]):
        """Update BM25 sparse index structures."""
        self._n_docs = len(texts)
        self._bm25_doc_freqs = []
        self._bm25_doc_freq = defaultdict(int)
        
        total_len = 0
        for text in texts:
            tokens = self._tokenize(text)
            total_len += len(tokens)
            freq_dict = defaultdict(int)
            for token in tokens:
                freq_dict[token] += 1
            self._bm25_doc_freqs.append(freq_dict)
            for token in freq_dict:
                self._bm25_doc_freq[token] += 1
                
        self._avgdl = total_len / self._n_docs if self._n_docs > 0 else 0

    def _bm25_score(self, query_tokens: List[str], doc_idx: int) -> float:
        """Calculate BM25 score for a single document."""
        k1 = 1.5
        b = 0.75
        score = 0.0
        doc_freqs = self._bm25_doc_freqs[doc_idx]
        dl = sum(doc_freqs.values())
        
        for q_token in query_tokens:
            if q_token not in doc_freqs:
                continue
            tf = doc_freqs[q_token]
            df = self._bm25_doc_freq[q_token]
            idf = math.log(1 + (self._n_docs - df + 0.5) / (df + 0.5))
            score += idf * (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * (dl / self._avgdl)))
        return score

    async def build_index(self, limit: int = 1000) -> int:
        """Build an in-memory search index from stored traces."""
        tracer = get_tracer()
        if not tracer:
            return 0

        traces = await tracer.query(limit=limit)
        engine = self._get_engine()
        texts = []
        trace_metas = []

        for t in traces:
            trace_id = t.get("trace_id", "")
            if not trace_id:
                continue
            spans = await tracer.get_spans(trace_id)
            text = await self._build_text(t, spans)
            texts.append(text)
            trace_metas.append({
                "trace_id": trace_id,
                "agent_name": t.get("agent_name", ""),
                "status": t.get("status", ""),
                "duration_ms": t.get("duration_ms", 0),
                "total_cost": t.get("total_cost", 0),
            })

        if not texts:
            return 0

        embeddings = await engine.embed(texts)
        self._update_bm25_index(texts)

        self._index = []
        for meta, emb, text in zip(trace_metas, embeddings, texts):
            self._index.append({**meta, "_embedding": emb, "text_snippet": text[:500]})

        logger.info(f"Indexed {len(self._index)} traces for hybrid semantic search")
        return len(self._index)

    def start_continuous_indexing(self, interval_seconds: int = 60):
        """Start a background worker that continuously updates the index."""
        if self._indexing_task is None or self._indexing_task.done():
            async def _indexer_loop():
                while True:
                    try:
                        await self.build_index()
                    except Exception as e:
                        logger.error(f"Continuous indexing failed: {e}")
                    await asyncio.sleep(interval_seconds)
            
            self._indexing_task = asyncio.create_task(_indexer_loop())
            logger.info("Started Continuous Background Indexer for Hybrid Search")

    async def search(self, query: str, time_range: str = "last_7d", top_k: int = 20) -> List[Dict[str, Any]]:
        """Search traces using Hybrid Reciprocal Rank Fusion (Dense + Sparse)."""
        logger.info(f"Hybrid search for '{query}' in {time_range}")

        if not self._index:
            count = await self.build_index()
            if count == 0:
                return []

        engine = self._get_engine()
        query_vectors = await engine.embed([query])
        if not query_vectors:
            return []

        query_vec = query_vectors[0]
        query_tokens = self._tokenize(query)

        # Compute Dense (Cosine) and Sparse (BM25) scores
        dense_results = []
        sparse_results = []
        
        for i, entry in enumerate(self._index):
            emb = entry["_embedding"]
            cosine_score = self._cosine_similarity(query_vec, emb)
            dense_results.append((i, cosine_score))
            
            bm25_val = self._bm25_score(query_tokens, i)
            sparse_results.append((i, bm25_val))

        # Sort independently
        dense_results.sort(key=lambda x: x[1], reverse=True)
        sparse_results.sort(key=lambda x: x[1], reverse=True)

        # Reciprocal Rank Fusion (RRF)
        k = 60 # RRF constant
        rrf_scores = defaultdict(float)
        
        for rank, (doc_idx, _) in enumerate(dense_results):
            rrf_scores[doc_idx] += 1.0 / (k + rank + 1)
            
        for rank, (doc_idx, _) in enumerate(sparse_results):
            rrf_scores[doc_idx] += 1.0 / (k + rank + 1)
            
        # Compile final ranked results
        final_results = []
        for doc_idx, score in sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)[:top_k]:
            entry = self._index[doc_idx]
            final_results.append({
                "trace_id": entry["trace_id"],
                "agent_name": entry["agent_name"],
                "status": entry["status"],
                "duration_ms": entry["duration_ms"],
                "total_cost": entry["total_cost"],
                "text_snippet": entry.get("text_snippet", ""),
                "score": round(score, 4),
                "trace": entry, # Include full trace for RAG context
            })

        return final_results

    @staticmethod
    def _cosine_similarity(a: List[float], b: List[float]) -> float:
        """Compute cosine similarity between two vectors."""
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)


# Module-level convenience function
async def semantic_search(query: str, time_range: str = "last_7d", top_k: int = 20) -> List[Dict[str, Any]]:
    """Search traces by meaning. Convenience wrapper around SemanticSearcher."""
    searcher = SemanticSearcher()
    return await searcher.search(query, time_range=time_range, top_k=top_k)
