# Module: `agent_tracer_plus.search.semantic`

Semantic search over traces using embedding similarity.

## Class `SemanticSearcher`
Natural language search across traces using hybrid vector + BM25 similarity (RRF).

### `def __init__(self, embedding_engine)`
### `def _get_engine(self)`
### `def _tokenize(self, text)`
### `def _update_bm25_index(self, texts)`
Update BM25 sparse index structures.

### `def _bm25_score(self, query_tokens, doc_idx)`
Calculate BM25 score for a single document.

### `def start_continuous_indexing(self, interval_seconds)`
Start a background worker that continuously updates the index.

### `def _cosine_similarity(a, b)`
Compute cosine similarity between two vectors.

