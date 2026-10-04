"""
Flowmint AI — Fireworks AI LLM Provider.

Calls Fireworks AI Chat Completions API with native tool/function calling support.
Uses official Fireworks AI OpenAI-compatible endpoint: https://api.fireworks.ai/inference/v1
Default model: accounts/fireworks/models/qwen3p8-max
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


DEFAULT_FIREWORKS_BASE_URL = "https://api.fireworks.ai/inference/v1"
DEFAULT_FIREWORKS_MODEL = "accounts/fireworks/models/qwen3p8-max"


class FireworksProvider(LLMProvider):
    """Fireworks AI provider implementation supporting OpenAI-compatible chat completions and structured tool calling."""

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_FIREWORKS_MODEL,
        base_url: str = DEFAULT_FIREWORKS_BASE_URL,
    ):
        if not api_key or not api_key.strip():
            raise FlowmintError(
                "Fireworks API key is required when AI_PROVIDER='fireworks'. Set FIREWORKS_API_KEY in environment.",
                code="AI_CONFIG_ERROR",
                status_code=500,
            )
        self.api_key = api_key.strip()
        self.model = model or DEFAULT_FIREWORKS_MODEL
        self.base_url = (base_url or DEFAULT_FIREWORKS_BASE_URL).rstrip("/")

    @property
    def provider_name(self) -> str:
        return "fireworks"

    async def generate(
        self,
        messages: list[LLMMessage],
        tools: list[dict] | None = None,
        temperature: float = 0.1,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        """
        Generate completion or structured function calls using Fireworks AI.
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        # Format messages for OpenAI/Fireworks Chat Completions schema
        formatted_messages: list[dict[str, Any]] = []
        for m in messages:
            msg: dict[str, Any] = {"role": m.role, "content": m.content or ""}
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
            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code
                error_body = exc.response.text
                raise FlowmintError(
                    f"Fireworks AI API HTTP {status_code} error: {error_body}",
                    code="AI_PROVIDER_ERROR",
                    status_code=502,
                ) from exc
            except httpx.HTTPError as exc:
                raise FlowmintError(
                    f"Fireworks AI API connection failed: {exc}",
                    code="AI_PROVIDER_ERROR",
                    status_code=502,
                ) from exc

        choices = data.get("choices", [])
        if not choices:
            raise FlowmintError(
                "Fireworks AI API returned empty choices list",
                code="AI_PROVIDER_ERROR",
                status_code=502,
            )

        choice = choices[0]
        msg = choice.get("message", {})
        tool_calls: list[ToolCallData] = []

        if "tool_calls" in msg and msg["tool_calls"]:
            for i, tc in enumerate(msg["tool_calls"]):
                fn = tc.get("function", {})
                raw_args = fn.get("arguments", {})
                if isinstance(raw_args, str):
                    try:
                        args = json.loads(raw_args)
                    except Exception:
                        args = {}
                elif isinstance(raw_args, dict):
                    args = raw_args
                else:
                    args = {}

                tool_id = tc.get("id") or f"call_fireworks_{i}"
                tool_name = fn.get("name", "")
                tool_calls.append(
                    ToolCallData(
                        id=tool_id,
                        function=FunctionCallData(name=tool_name, arguments=args),
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
