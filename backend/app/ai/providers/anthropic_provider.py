"""
Flowmint AI — Anthropic LLM Provider.

Calls Anthropic Messages API with tool-use capability.
"""

from __future__ import annotations

import json
from typing import Any

import httpx

from app.ai.providers.base import (
    FunctionCallData,
    LLMMessage,
    LLMProvider,
    LLMResponse,
    ToolCallData,
    UsageMetadata,
)
from app.core.exceptions import FlowmintError


class AnthropicProvider(LLMProvider):
    """Anthropic Claude API provider implementation."""

    def __init__(self, api_key: str, model: str = "claude-3-5-sonnet-20240620"):
        if not api_key:
            raise FlowmintError("Anthropic API key is required", code="AI_CONFIG_ERROR", status_code=500)
        self.api_key = api_key
        self.model = model
        self.base_url = "https://api.anthropic.com/v1"

    @property
    def provider_name(self) -> str:
        return "anthropic"

    async def generate(
        self,
        messages: list[LLMMessage],
        tools: list[dict] | None = None,
        temperature: float = 0.1,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        system_prompt = ""
        anthropic_messages: list[dict[str, Any]] = []

        for m in messages:
            if m.role == "system":
                system_prompt += f"{m.content}\n"
            elif m.role == "tool":
                anthropic_messages.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": m.tool_call_id or "tool_call_1",
                            "content": m.content,
                        }
                    ],
                })
            elif m.role == "assistant" and m.tool_calls:
                content_blocks: list[dict[str, Any]] = []
                if m.content:
                    content_blocks.append({"type": "text", "text": m.content})
                for tc in m.tool_calls:
                    content_blocks.append({
                        "type": "tool_use",
                        "id": tc.id,
                        "name": tc.function.name,
                        "input": tc.function.arguments,
                    })
                anthropic_messages.append({"role": "assistant", "content": content_blocks})
            else:
                anthropic_messages.append({"role": m.role, "content": m.content})

        payload: dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": anthropic_messages,
        }
        if system_prompt:
            payload["system"] = system_prompt.strip()

        if tools:
            anthropic_tools = []
            for t in tools:
                fn = t.get("function", {})
                anthropic_tools.append({
                    "name": fn.get("name"),
                    "description": fn.get("description", ""),
                    "input_schema": fn.get("parameters", {}),
                })
            payload["tools"] = anthropic_tools

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/messages",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
            except httpx.HTTPError as exc:
                raise FlowmintError(f"Anthropic API call failed: {exc}", code="AI_PROVIDER_ERROR", status_code=502) from exc

        content_text = ""
        tool_calls: list[ToolCallData] = []

        for block in data.get("content", []):
            if block["type"] == "text":
                content_text += block["text"]
            elif block["type"] == "tool_use":
                tool_calls.append(
                    ToolCallData(
                        id=block["id"],
                        function=FunctionCallData(name=block["name"], arguments=block.get("input", {})),
                    )
                )

        raw_usage = data.get("usage", {})
        usage = UsageMetadata(
            prompt_tokens=raw_usage.get("input_tokens", 0),
            completion_tokens=raw_usage.get("output_tokens", 0),
            total_tokens=raw_usage.get("input_tokens", 0) + raw_usage.get("output_tokens", 0),
        )

        return LLMResponse(
            content=content_text or None,
            tool_calls=tool_calls,
            finish_reason=data.get("stop_reason", "end_turn"),
            usage=usage,
        )
