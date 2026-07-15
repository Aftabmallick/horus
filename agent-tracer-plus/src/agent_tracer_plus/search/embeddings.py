"""Trace text-to-embedding engine."""

import asyncio
import logging
from typing import Any, List

logger = logging.getLogger(__name__)

# Lazy loaded module
_sentence_transformers = None

class EmbeddingEngine:
    """Generates embeddings for traces using a local or remote model."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self._model = None
        self._load_dependency()

    def _load_dependency(self) -> None:
        global _sentence_transformers
        if _sentence_transformers is None:
            try:
                import sentence_transformers
                _sentence_transformers = sentence_transformers
            except ImportError:
                logger.error("sentence-transformers is not installed. Please install with `pip install agent-tracer-plus[search]`")
                raise ImportError("sentence-transformers is required for EmbeddingEngine")

    def _get_model(self) -> Any:
        if self._model is None:
            logger.info(f"Loading embedding model {self.model_name}...")
            self._model = _sentence_transformers.SentenceTransformer(self.model_name)
        return self._model

    async def embed(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a list of texts."""
        if not texts:
            return []

        logger.debug(f"Generating embeddings for {len(texts)} texts using {self.model_name}")
        model = self._get_model()

        # Run synchronous encoding in an executor to avoid blocking the event loop
        loop = asyncio.get_running_loop()
        embeddings = await loop.run_in_executor(
            None,
            lambda: model.encode(texts, convert_to_numpy=True)
        )
        return embeddings.tolist()
