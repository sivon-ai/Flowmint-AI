"""
Flowmint AI — OpenAI LLM Provider.

Calls OpenAI Chat Completions API with native tool/function calling support.
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


class OpenAIProvider(LLMProvider):
    """OpenAI API provider implementation."""

    def __init__(self, api_key: str, model: str = "gpt-4o", base_url: str = "https://api.openai.com/v1"):
        if not api_key:
            raise FlowmintError("OpenAI API key is required", code="AI_CONFIG_ERROR", status_code=500)
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")

    @property
    def provider_name(self) -> str:
        return "openai"

    async def generate(
        self,
        messages: list[LLMMessage],
        tools: list[dict] | None = None,
        temperature: float = 0.1,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        # Format messages for OpenAI format
        formatted_messages: list[dict[str, Any]] = []
        for m in messages:
            msg: dict[str, Any] = {"role": m.role, "content": m.content}
            if m.tool_calls:
                msg["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments_json(),
                        },
                    }
                    for tc in m.tool_calls
                ]
            if m.tool_call_id:
                msg["tool_call_id"] = m.tool_call_id
            if m.name:
                msg["name"] = m.name
            formatted_messages.append(msg)

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": formatted_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
            except httpx.HTTPError as exc:
                raise FlowmintError(f"OpenAI API call failed: {exc}", code="AI_PROVIDER_ERROR", status_code=502) from exc

        choice = data["choices"][0]
        msg = choice["message"]
        tool_calls: list[ToolCallData] = []

        if "tool_calls" in msg and msg["tool_calls"]:
            for tc in msg["tool_calls"]:
                try:
                    args = json.loads(tc["function"]["arguments"])
                except Exception:
                    args = {}
                tool_calls.append(
                    ToolCallData(
                        id=tc["id"],
                        function=FunctionCallData(name=tc["function"]["name"], arguments=args),
                    )
                )

        raw_usage = data.get("usage", {})
        usage = UsageMetadata(
            prompt_tokens=raw_usage.get("prompt_tokens", 0),
            completion_tokens=raw_usage.get("completion_tokens", 0),
            total_tokens=raw_usage.get("total_tokens", 0),
        )

        return LLMResponse(
            content=msg.get("content"),
            tool_calls=tool_calls,
            finish_reason=choice.get("finish_reason", "stop"),
            usage=usage,
        )
