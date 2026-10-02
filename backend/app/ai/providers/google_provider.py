"""
Flowmint AI — Google Gemini LLM Provider.

Calls Google Generative Language API with function calling support.
"""

from __future__ import annotations

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


class GoogleProvider(LLMProvider):
    """Google Gemini API provider implementation."""

    def __init__(self, api_key: str, model: str = "gemini-1.5-pro"):
        if not api_key:
            raise FlowmintError("Google API key is required", code="AI_CONFIG_ERROR", status_code=500)
        self.api_key = api_key
        self.model = model
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"

    @property
    def provider_name(self) -> str:
        return "google"

    async def generate(
        self,
        messages: list[LLMMessage],
        tools: list[dict] | None = None,
        temperature: float = 0.1,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        url = f"{self.base_url}/models/{self.model}:generateContent?key={self.api_key}"

        contents: list[dict[str, Any]] = []
        for m in messages:
            role = "user" if m.role in ["user", "system"] else "model"
            parts: list[dict[str, Any]] = []

            if m.content:
                parts.append({"text": m.content})

            if m.tool_calls:
                for tc in m.tool_calls:
                    parts.append({
                        "functionCall": {
                            "name": tc.function.name,
                            "args": tc.function.arguments,
                        }
                    })

            if m.role == "tool":
                role = "function"
                parts = [{
                    "functionResponse": {
                        "name": m.name or "tool",
                        "response": {"output": m.content},
                    }
                }]

            if parts:
                contents.append({"role": role, "parts": parts})

        payload: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }

        if tools:
            declarations = []
            for t in tools:
                fn = t.get("function", {})
                declarations.append({
                    "name": fn.get("name"),
                    "description": fn.get("description", ""),
                    "parameters": fn.get("parameters", {}),
                })
            payload["tools"] = [{"functionDeclarations": declarations}]

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
            except httpx.HTTPError as exc:
                raise FlowmintError(f"Google Gemini API call failed: {exc}", code="AI_PROVIDER_ERROR", status_code=502) from exc

        candidates = data.get("candidates", [])
        if not candidates:
            return LLMResponse(content="")

        cand = candidates[0]
        parts = cand.get("content", {}).get("parts", [])
        content_text = ""
        tool_calls: list[ToolCallData] = []

        for p in parts:
            if "text" in p:
                content_text += p["text"]
            elif "functionCall" in p:
                fc = p["functionCall"]
                tool_calls.append(
                    ToolCallData(
                        id=f"call_{fc['name']}",
                        function=FunctionCallData(name=fc["name"], arguments=fc.get("args", {})),
                    )
                )

        usage_meta = data.get("usageMetadata", {})
        usage = UsageMetadata(
            prompt_tokens=usage_meta.get("promptTokenCount", 0),
            completion_tokens=usage_meta.get("candidatesTokenCount", 0),
            total_tokens=usage_meta.get("totalTokenCount", 0),
        )

        return LLMResponse(
            content=content_text or None,
            tool_calls=tool_calls,
            finish_reason=cand.get("finishReason", "STOP"),
            usage=usage,
        )
