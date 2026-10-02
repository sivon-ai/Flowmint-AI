"""
Flowmint AI — AI Provider Abstraction.

Defines the unified, provider-agnostic interface for LLM operations.
Supports OpenAI, Anthropic, Google Gemini, and Mock providers.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class FunctionCallData:
    """Structured tool/function call payload."""
    name: str
    arguments: dict[str, Any]

    def arguments_json(self) -> str:
        return json.dumps(self.arguments)


@dataclass
class ToolCallData:
    """Individual tool call requested by the model."""
    id: str
    function: FunctionCallData


@dataclass
class UsageMetadata:
    """Token consumption metrics."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass
class LLMMessage:
    """Unified message structure across all LLM providers."""
    role: str  # system, user, assistant, tool
    content: str = ""
    tool_calls: list[ToolCallData] | None = None
    tool_call_id: str | None = None
    name: str | None = None


@dataclass
class LLMResponse:
    """Standardized response from any LLM provider."""
    content: str | None = None
    tool_calls: list[ToolCallData] = field(default_factory=list)
    finish_reason: str = "stop"  # stop, tool_calls, length
    usage: UsageMetadata = field(default_factory=UsageMetadata)


class LLMProvider(ABC):
    """Abstract base class for all LLM providers."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Name of the provider (mock, openai, anthropic, google)."""
        pass

    @abstractmethod
    async def generate(
        self,
        messages: list[LLMMessage],
        tools: list[dict] | None = None,
        temperature: float = 0.1,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        """Generate a response or request tool calls from the model."""
        pass
