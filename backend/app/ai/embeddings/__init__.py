"""Flowmint AI — Embeddings Module."""

from app.ai.embeddings.base import EmbeddingProvider
from app.ai.embeddings.factory import get_embedding_provider
from app.ai.embeddings.mock import MockEmbeddingProvider

__all__ = [
    "EmbeddingProvider",
    "get_embedding_provider",
    "MockEmbeddingProvider",
]
