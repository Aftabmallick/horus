"""Failure clustering using HDBSCAN and UMAP on trace embeddings."""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any, Dict, List, Optional

import json
from agent_tracer_plus.core.context import get_tracer
from agent_tracer_plus.search.embeddings import EmbeddingEngine

logger = logging.getLogger(__name__)


class TraceClustering:
    """Cluster similar traces (especially failures) to find patterns."""

    def __init__(self, embedding_engine: Optional[EmbeddingEngine] = None):
        self._engine = embedding_engine or EmbeddingEngine()
        self._embeddings: List[List[float]] = []
        self._trace_metas: List[Dict[str, Any]] = []
        
    async def _generate_cluster_name(self, sample_texts: List[str]) -> str:
        """Use an LLM to generate a descriptive name for a cluster based on samples."""
        try:
            import litellm
            prompt = (
                "You are an expert root-cause analyzer. I will provide you with several sample traces "
                "from a specific failure cluster. Generate a concise, descriptive name (3-5 words) "
                "for this cluster that captures the core issue (e.g., 'Postgres Timeout Errors', "
                "'Hallucinated JSON Formatting').\n\nSamples:\n" + "\n---\n".join(sample_texts[:3])
            )
            response = await litellm.acompletion(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}]
            )
            return response.choices[0].message.content.strip()
        except ImportError:
            return "Failure Cluster (LLM Naming Disabled)"
        except Exception as e:
            logger.warning(f"Failed to generate cluster name: {e}")
            return "Unknown Error Cluster"

    async def cluster_traces(
        self,
        filter_dict: Optional[Dict[str, Any]] = None,
        n_clusters: int = 10,
    ) -> List[Dict[str, Any]]:
        """Cluster traces matching the filter into n_clusters groups."""
        tracer = get_tracer()
        if not tracer:
            return []

        traces = await tracer.query(limit=5000)

        # Apply filter
        if filter_dict:
            status = filter_dict.get("status")
            if status:
                traces = [t for t in traces if t.get("status") == status]

        if len(traces) < 2:
            return [{"cluster_id": 0, "count": len(traces), "traces": traces, "description": "Single cluster"}]

        # Extract spans for rich text representation
        texts = []
        trace_id_to_text = {}
        for t in traces:
            trace_id = t.get("trace_id")
            spans = await tracer.get_spans(trace_id)
            parts = [t.get("agent_name", ""), t.get("status", "")]
            for s in spans:
                if s.error:
                    parts.append(f"Error: {s.error.get('message', '')}")
            text_repr = " ".join(parts)
            texts.append(text_repr)
            trace_id_to_text[trace_id] = text_repr

        # Generate embeddings
        embeddings = await self._engine.embed(texts)
        if not embeddings:
            return []

        try:
            import numpy as np
            from umap import UMAP
            import hdbscan
            
            # Dimensionality reduction
            umap_reducer = UMAP(n_components=5, metric='cosine', random_state=42)
            reduced_embeddings = umap_reducer.fit_transform(embeddings)
            
            # Density-based clustering
            clusterer = hdbscan.HDBSCAN(min_cluster_size=max(2, len(traces) // 20), metric='euclidean')
            cluster_labels = clusterer.fit_predict(reduced_embeddings)
            
        except ImportError:
            logger.warning("umap-learn or hdbscan not installed. Falling back to simple text matching.")
            cluster_labels = [ hash(t.get('agent_name', '')) % n_clusters for t in traces ]

        # Group by labels
        clusters: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
        for t, label in zip(traces, cluster_labels):
            # label -1 is noise in HDBSCAN
            clusters[label].append(t)

        # Format output
        result = []
        for cluster_id, members in sorted(clusters.items(), key=lambda x: -len(x[1])):
            if cluster_id == -1:
                # Noise cluster
                name = "Uncategorized Noise"
            else:
                sample_texts = [trace_id_to_text[m.get("trace_id")] for m in members[:3]]
                name = await self._generate_cluster_name(sample_texts)

            result.append({
                "cluster_id": int(cluster_id),
                "count": len(members),
                "name": name,
                "avg_duration_ms": round(sum(m.get("duration_ms", 0) for m in members) / len(members), 2),
                "avg_cost": round(sum(m.get("total_cost", 0) for m in members) / len(members), 6),
                "sample_trace_ids": [m.get("trace_id", "") for m in members[:5]],
            })
            if len(result) >= n_clusters:
                break

        logger.info(f"Clustered {len(traces)} traces into {len(result)} groups")
        return result


# Module-level convenience
async def cluster_traces(filter_dict: Optional[Dict[str, Any]] = None, n_clusters: int = 10) -> List[Dict[str, Any]]:
    """Cluster similar traces. Convenience wrapper."""
    clusterer = TraceClustering()
    return await clusterer.cluster_traces(filter_dict=filter_dict, n_clusters=n_clusters)
