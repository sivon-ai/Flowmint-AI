"""
Flowmint AI — OpenAI Embedding Provider.

Calls OpenAI Embeddings API (e.g. text-embedding-3-small).
"""

from __future__ import annotations

import httpx

from app.ai.embeddings.base import EmbeddingProvider
from app.core.exceptions import FlowmintError


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """OpenAI Embeddings API implementation."""

    def __init__(self, api_key: str, model: str = "text-embedding-3-small", dimension: int = 1536):
        if not api_key:
            raise FlowmintError("OpenAI API key is required", code="AI_CONFIG_ERROR", status_code=500)
        self.api_key = api_key
        self.model = model
        self._dim = dimension
        self.base_url = "https://api.openai.com/v1"

    @property
    def dimension(self) -> int:
        return self._dim

    async def embed_text(self, text: str) -> list[float]:
        res = await self.embed_batch([text])
        return res[0]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "input": texts,
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/embeddings",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
                return [item["embedding"] for item in data.get("data", [])]
            except httpx.HTTPError as exc:
                raise FlowmintError(f"OpenAI Embedding API call failed: {exc}", code="AI_PROVIDER_ERROR", status_code=502) from exc
