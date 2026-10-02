"""
Flowmint AI — Mock Embedding Provider.

Generates deterministic normalized pseudorandom float vectors based on text hashes.
Used for zero-network unit tests and local development.
"""

from __future__ import annotations

import hashlib
import math
import struct

from app.ai.embeddings.base import EmbeddingProvider


class MockEmbeddingProvider(EmbeddingProvider):
    """Deterministic embedding provider."""

    def __init__(self, dimension: int = 1536):
        self._dim = dimension

    @property
    def dimension(self) -> int:
        return self._dim

    async def embed_text(self, text: str) -> list[float]:
        # Hash text using sha256 to create deterministic seed
        seed_bytes = hashlib.sha256(text.encode("utf-8")).digest()
        seed_int = struct.unpack(">I", seed_bytes[:4])[0]

        # Generate dim floats deterministically
        raw_vec = []
        val = seed_int
        for _ in range(self._dim):
            # Simple LCG
            val = (val * 1103515245 + 12345) & 0x7FFFFFFF
            norm = (val / 0x7FFFFFFF) * 2.0 - 1.0
            raw_vec.append(norm)

        # Normalize to unit length
        magnitude = math.sqrt(sum(x * x for x in raw_vec)) or 1.0
        return [x / magnitude for x in raw_vec]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [await self.embed_text(t) for t in texts]
