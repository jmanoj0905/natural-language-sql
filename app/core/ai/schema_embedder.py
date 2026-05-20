"""Sentence-transformer embedder for schema docs and queries."""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

import numpy as np

from app.exceptions import EmbedderUnavailableError
from app.utils.logger import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


class SchemaEmbedder:
    MODEL = "all-MiniLM-L6-v2"
    DIM = 384

    def __init__(self) -> None:
        self._model = None  # lazy

    def _ensure_model(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as e:
                logger.warning("sentence_transformers_import_failed", error=str(e))
                raise EmbedderUnavailableError(
                    f"sentence-transformers not installed: {e}"
                )
            try:
                self._model = SentenceTransformer(self.MODEL)
            except Exception as e:
                logger.warning("embedder_model_load_failed", error=str(e))
                raise EmbedderUnavailableError(
                    f"Failed to load embedder model {self.MODEL}: {e}"
                )
        return self._model

    def embed(self, texts: list[str]) -> np.ndarray:
        """Return L2-normalized vectors of shape (len(texts), DIM)."""
        model = self._ensure_model()
        vecs = model.encode(
            texts,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return vecs.astype(np.float32)


@lru_cache(maxsize=1)
def get_schema_embedder() -> SchemaEmbedder:
    return SchemaEmbedder()
