"""
Unit tests for AI Provider and Embedding Provider abstractions.
"""

import math
import pytest

from app.ai.embeddings.factory import get_embedding_provider
from app.ai.embeddings.mock import MockEmbeddingProvider
from app.ai.providers.base import LLMMessage, LLMResponse, ToolCallData, FunctionCallData
from app.ai.providers.factory import get_llm_provider
from app.ai.providers.mock import MockLLMProvider
from app.ai.providers.openai_provider import OpenAIProvider
from app.config import Settings
from app.core.exceptions import FlowmintError


class TestLLMProviders:
    @pytest.mark.asyncio
    async def test_mock_llm_provider_conversational(self):
        provider = MockLLMProvider()
        messages = [LLMMessage(role="user", content="Hello there!")]
        resp = await provider.generate(messages=messages)
        assert resp.content is not None
        assert len(resp.tool_calls) == 0
        assert resp.usage.total_tokens > 0

    @pytest.mark.asyncio
    async def test_mock_llm_provider_tool_selection(self):
        provider = MockLLMProvider()
        tools = [
            {
                "type": "function",
                "function": {"name": "search_products", "description": "Search products"},
            }
        ]
        messages = [LLMMessage(role="user", content="Find me a laptop under 50000")]
        resp = await provider.generate(messages=messages, tools=tools)
        assert resp.finish_reason == "tool_calls"
        assert len(resp.tool_calls) == 1
        assert resp.tool_calls[0].function.name == "search_products"
        assert resp.tool_calls[0].function.arguments["max_price"] == 50000.0

    @pytest.mark.asyncio
    async def test_mock_llm_provider_preset_queue(self):
        provider = MockLLMProvider()
        preset = LLMResponse(content="Custom Preset Response", finish_reason="stop")
        provider.enqueue_response(preset)

        resp = await provider.generate(messages=[LLMMessage(role="user", content="any")])
        assert resp.content == "Custom Preset Response"

    def test_provider_factory(self):
        s_mock = Settings(ai_provider="mock")
        assert isinstance(get_llm_provider(s_mock), MockLLMProvider)

        s_err = Settings(ai_provider="openai", openai_api_key="")
        with pytest.raises(FlowmintError):
            get_llm_provider(s_err)


class TestEmbeddingProviders:
    @pytest.mark.asyncio
    async def test_mock_embedding_dimensions_and_normalization(self):
        provider = MockEmbeddingProvider(dimension=128)
        assert provider.dimension == 128

        vec1 = await provider.embed_text("laptop with 16gb ram")
        assert len(vec1) == 128

        # Verify unit normalization: sqrt(sum(x^2)) ~= 1.0
        magnitude = math.sqrt(sum(x * x for x in vec1))
        assert abs(magnitude - 1.0) < 1e-4

        # Deterministic: identical text yields identical vector
        vec2 = await provider.embed_text("laptop with 16gb ram")
        assert vec1 == vec2

        # Distinct text yields different vector
        vec3 = await provider.embed_text("running shoes for marathon")
        assert vec1 != vec3

    @pytest.mark.asyncio
    async def test_mock_embedding_batch(self):
        provider = MockEmbeddingProvider(dimension=64)
        texts = ["apple", "banana", "cherry"]
        batch = await provider.embed_batch(texts)
        assert len(batch) == 3
        for v in batch:
            assert len(v) == 64

    def test_embedding_factory(self):
        s = Settings(embedding_provider="mock")
        provider = get_embedding_provider(s)
        assert isinstance(provider, MockEmbeddingProvider)
