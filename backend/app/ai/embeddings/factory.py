"""
Flowmint AI — Embedding Provider Factory.
"""

from __future__ import annotations

from app.ai.embeddings.base import EmbeddingProvider
from app.ai.embeddings.mock import MockEmbeddingProvider
from app.ai.embeddings.openai_embedding import OpenAIEmbeddingProvider
from app.config import Settings, get_settings


def get_embedding_provider(settings: Settings | None = None) -> EmbeddingProvider:
    """Factory to return the active embedding provider."""
    cfg = settings or get_settings()
    provider_name = cfg.embedding_provider.lower().strip()

    if provider_name == "openai" and cfg.openai_api_key:
        return OpenAIEmbeddingProvider(
            api_key=cfg.openai_api_key,
            model=cfg.embedding_model,
        )
    return MockEmbeddingProvider()
