"""
Flowmint AI — LLM Provider Factory.

Instantiates the configured LLM provider according to application settings.
"""

from __future__ import annotations

from app.ai.providers.anthropic_provider import AnthropicProvider
from app.ai.providers.base import LLMProvider
from app.ai.providers.fireworks_provider import FireworksProvider
from app.ai.providers.google_provider import GoogleProvider
from app.ai.providers.mock import MockLLMProvider
from app.ai.providers.openai_provider import OpenAIProvider
from app.config import Settings, get_settings


def get_llm_provider(settings: Settings | None = None) -> LLMProvider:
    """Factory to return the active LLM provider."""
    cfg = settings or get_settings()
    provider_name = cfg.ai_provider.lower().strip()

    if provider_name == "fireworks":
        model = cfg.fireworks_model
        if cfg.ai_model and cfg.ai_model != "mock-model":
            model = cfg.ai_model
        return FireworksProvider(
            api_key=cfg.fireworks_api_key,
            model=model,
            base_url=cfg.fireworks_base_url,
        )
    elif provider_name == "openai":
        return OpenAIProvider(
            api_key=cfg.openai_api_key,
            model=cfg.ai_model if cfg.ai_model != "mock-model" else "gpt-4o",
        )
    elif provider_name == "anthropic":
        return AnthropicProvider(
            api_key=cfg.anthropic_api_key,
            model=cfg.ai_model if cfg.ai_model != "mock-model" else "claude-3-5-sonnet-20240620",
        )
    elif provider_name in ["google", "gemini"]:
        return GoogleProvider(
            api_key=cfg.google_api_key,
            model=cfg.ai_model if cfg.ai_model != "mock-model" else "gemini-1.5-pro",
        )
    else:
        # Default to Mock provider for local development, testing, and offline modes
        return MockLLMProvider(model_name=cfg.ai_model)
