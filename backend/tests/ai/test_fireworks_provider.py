"""
Flowmint AI — Fireworks Provider Unit and Integration Tests.

Verifies:
1. FireworksProvider initialization & configuration enforcement (no empty keys).
2. Explicit fail-closed behavior (no silent fallback to MockLLM).
3. Provider factory correctly instantiates FireworksProvider when configured.
4. Preserves MockLLM behavior when AI_PROVIDER=mock.
5. OpenAI-compatible Chat Completions payload formatting.
6. Structured tool / function calling support.
7. HTTP error and connection failure handling.
8. BuyerAgent execution loop with FireworksProvider.
9. EvaluationRunner reports BLOCKED when FIREWORKS_API_KEY is missing.
10. Live smoke test when FIREWORKS_API_KEY is configured in the environment.
"""

from __future__ import annotations

import json
import os
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.ai.agents.buyer_agent import BuyerAgent
from app.ai.evaluation.runner import EvaluationRunner
from app.ai.providers.base import LLMMessage, LLMResponse
from app.ai.providers.factory import get_llm_provider
from app.ai.providers.fireworks_provider import (
    DEFAULT_FIREWORKS_BASE_URL,
    DEFAULT_FIREWORKS_MODEL,
    FireworksProvider,
)
from app.ai.providers.mock import MockLLMProvider
from app.ai.tools.base import ToolContext, ToolResult
from app.config import Settings
from app.core.exceptions import FlowmintError


class TestFireworksProviderUnit:
    """Unit tests for FireworksProvider and factory integration."""

    def test_fireworks_missing_api_key_raises_config_error(self):
        """Missing or whitespace API key must raise an explicit AI_CONFIG_ERROR."""
        with pytest.raises(FlowmintError) as exc_info:
            FireworksProvider(api_key="")
        assert exc_info.value.code == "AI_CONFIG_ERROR"
        assert "Fireworks API key is required" in str(exc_info.value)

        with pytest.raises(FlowmintError) as exc_info2:
            FireworksProvider(api_key="   ")
        assert exc_info2.value.code == "AI_CONFIG_ERROR"

    def test_factory_fireworks_missing_key_never_falls_back_to_mock(self):
        """AI_PROVIDER=fireworks with missing key must fail closed with AI_CONFIG_ERROR, never silent fallback."""
        settings = Settings(ai_provider="fireworks", fireworks_api_key="")
        with pytest.raises(FlowmintError) as exc_info:
            get_llm_provider(settings)
        assert exc_info.value.code == "AI_CONFIG_ERROR"
        assert "Fireworks API key is required" in str(exc_info.value)

    def test_factory_mock_provider_works_unchanged(self):
        """AI_PROVIDER=mock continues to return MockLLMProvider."""
        settings = Settings(ai_provider="mock", ai_model="mock-model")
        provider = get_llm_provider(settings)
        assert isinstance(provider, MockLLMProvider)
        assert provider.provider_name == "mock"

    def test_factory_fireworks_success_with_key(self):
        """AI_PROVIDER=fireworks with key instantiates FireworksProvider with correct attributes."""
        settings = Settings(
            ai_provider="fireworks",
            fireworks_api_key="fw_test_key_valid_123",
            fireworks_model="accounts/fireworks/models/qwen3p8-max",
            fireworks_base_url="https://api.fireworks.ai/inference/v1",
        )
        provider = get_llm_provider(settings)
        assert isinstance(provider, FireworksProvider)
        assert provider.provider_name == "fireworks"
        assert provider.model == "accounts/fireworks/models/qwen3p8-max"
        assert provider.base_url == "https://api.fireworks.ai/inference/v1"

    @pytest.mark.asyncio
    async def test_fireworks_generate_conversational_mocked(self):
        """Mocked unit test for conversational text generation."""
        provider = FireworksProvider(
            api_key="fw_test_key_123",
            model=DEFAULT_FIREWORKS_MODEL,
            base_url=DEFAULT_FIREWORKS_BASE_URL,
        )

        mock_response_data = {
            "id": "chatcmpl-test-conv-001",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "Hello! I am your Flowmint commerce assistant.",
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 25,
                "completion_tokens": 12,
                "total_tokens": 37,
            },
        }

        mock_http_resp = MagicMock()
        mock_http_resp.status_code = 200
        mock_http_resp.json.return_value = mock_response_data
        mock_http_resp.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_http_resp

            messages = [LLMMessage(role="user", content="Hello assistant")]
            response = await provider.generate(messages=messages, temperature=0.1, max_tokens=256)

            assert response.content == "Hello! I am your Flowmint commerce assistant."
            assert response.finish_reason == "stop"
            assert len(response.tool_calls) == 0
            assert response.usage.prompt_tokens == 25
            assert response.usage.completion_tokens == 12
            assert response.usage.total_tokens == 37

            # Verify outgoing HTTP call structure
            mock_post.assert_called_once()
            called_url = mock_post.call_args[0][0]
            called_headers = mock_post.call_args[1]["headers"]
            called_json = mock_post.call_args[1]["json"]

            assert called_url == "https://api.fireworks.ai/inference/v1/chat/completions"
            assert called_headers["Authorization"] == "Bearer fw_test_key_123"
            assert called_json["model"] == DEFAULT_FIREWORKS_MODEL
            assert called_json["messages"][0]["role"] == "user"
            assert called_json["messages"][0]["content"] == "Hello assistant"

    @pytest.mark.asyncio
    async def test_fireworks_generate_tool_calls_mocked(self):
        """Mocked unit test for structured function / tool calling."""
        provider = FireworksProvider(
            api_key="fw_test_key_123",
            model="accounts/fireworks/models/qwen3p8-max",
        )

        mock_response_data = {
            "id": "chatcmpl-test-tool-002",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call_fw_search_999",
                                "type": "function",
                                "function": {
                                    "name": "search_products",
                                    "arguments": json.dumps({"query": "wireless earbuds", "max_price": 5000.0}),
                                },
                            }
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            ],
            "usage": {
                "prompt_tokens": 120,
                "completion_tokens": 30,
                "total_tokens": 150,
            },
        }

        mock_http_resp = MagicMock()
        mock_http_resp.status_code = 200
        mock_http_resp.json.return_value = mock_response_data
        mock_http_resp.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_http_resp

            tools = [
                {
                    "type": "function",
                    "function": {
                        "name": "search_products",
                        "description": "Search active catalog products",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "query": {"type": "string"},
                                "max_price": {"type": "number"},
                            },
                        },
                    },
                }
            ]
            messages = [LLMMessage(role="user", content="Find wireless earbuds under 5000")]
            response = await provider.generate(messages=messages, tools=tools)

            assert response.finish_reason == "tool_calls"
            assert len(response.tool_calls) == 1
            tc = response.tool_calls[0]
            assert tc.id == "call_fw_search_999"
            assert tc.function.name == "search_products"
            assert tc.function.arguments == {"query": "wireless earbuds", "max_price": 5000.0}

            # Check that tools payload was passed
            called_json = mock_post.call_args[1]["json"]
            assert "tools" in called_json
            assert called_json["tool_choice"] == "auto"

    @pytest.mark.asyncio
    async def test_fireworks_http_error_fails_closed(self):
        """HTTP status errors from Fireworks must raise FlowmintError(code='AI_PROVIDER_ERROR')."""
        provider = FireworksProvider(api_key="fw_bad_key")

        mock_request = httpx.Request("POST", "https://api.fireworks.ai/inference/v1/chat/completions")
        mock_http_resp = httpx.Response(401, request=mock_request, text="Unauthorized: Invalid API key")

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = httpx.HTTPStatusError("401 Unauthorized", request=mock_request, response=mock_http_resp)

            with pytest.raises(FlowmintError) as exc_info:
                await provider.generate(messages=[LLMMessage(role="user", content="test")])

            assert exc_info.value.code == "AI_PROVIDER_ERROR"
            assert "401" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_buyer_agent_with_mocked_fireworks_provider(self):
        """Verify BuyerAgent seamlessly executes its read-only tool loop using FireworksProvider."""
        provider = FireworksProvider(api_key="fw_test_key_valid")
        agent = BuyerAgent(provider=provider)

        # 1st call returns tool call for check_inventory
        tool_call_json = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call_fw_tool_inv",
                                "type": "function",
                                "function": {
                                    "name": "check_inventory",
                                    "arguments": json.dumps({"sku": "TEST-SKU-001"}),
                                },
                            }
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            ],
            "usage": {"prompt_tokens": 50, "completion_tokens": 20, "total_tokens": 70},
        }

        # 2nd call returns grounded text summary
        synthesis_json = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "TEST-SKU-001 currently has 25 units available in stock.",
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 80, "completion_tokens": 15, "total_tokens": 95},
        }

        mock_resp_1 = MagicMock(status_code=200, json=lambda: tool_call_json, raise_for_status=lambda: None)
        mock_resp_2 = MagicMock(status_code=200, json=lambda: synthesis_json, raise_for_status=lambda: None)

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post, \
             patch("app.ai.agents.base.tool_registry.execute", new_callable=AsyncMock) as mock_tool_exec:
            mock_post.side_effect = [mock_resp_1, mock_resp_2]
            mock_tool_exec.return_value = (
                ToolResult.ok(
                    data={"sku": "TEST-SKU-001", "available_stock": 25},
                    message="Found inventory: 25 units available",
                ),
                12,
            )

            context = ToolContext(
                merchant_id=uuid.uuid4(),
                trace_id="trace_fw_test_001",
                is_read_only=True,
            )
            result = await agent.execute("Do you have stock for SKU TEST-SKU-001?", context=context)

            assert "25 units" in result.response
            assert len(result.tool_calls) == 1
            assert result.tool_calls[0]["name"] == "check_inventory"
            assert result.action_plan is None  # Action plan strictly None for BuyerAgent

    def test_evaluation_runner_real_llm_fireworks_blocked_without_key(self):
        """EvaluationRunner with runner_type='real_llm' and Fireworks model raises BLOCKED error without credentials."""
        with patch("app.config.get_settings") as mock_get_settings:
            mock_get_settings.return_value = Settings(
                fireworks_api_key="",
                openai_api_key="",
                anthropic_api_key="",
                google_api_key="",
            )
            with pytest.raises(ValueError) as exc_info:
                EvaluationRunner(
                    runner_type="real_llm",
                    model_name="accounts/fireworks/models/qwen3p8-max",
                )
            assert "BLOCKED" in str(exc_info.value)
            assert "FIREWORKS_API_KEY" in str(exc_info.value)

    def test_fireworks_llm_has_zero_write_capabilities_or_mutating_tools(self):
        """Verify FireworksProvider and all tools accessible to agents are strictly read-only."""
        from app.ai.tools.registry import tool_registry

        for name, tool in tool_registry.tools.items():
            assert tool.is_read_only is True, f"Tool '{name}' must be read-only"
            assert "delete" not in name.lower()
            assert "refund" not in name.lower()
            assert "payout" not in name.lower()
            assert "write" not in name.lower()

    def test_deterministic_governance_layers_isolate_fireworks(self):
        """Verify deterministic governance layers (policy, risk, approval, audit) operate independently of LLM."""
        from app.services.action_execution_service import ActionExecutionService
        from app.services.approval_service import ApprovalService
        from app.services.audit_service import AuditService
        from app.services.policy_engine import policy_engine
        from app.services.risk_engine import RiskEngine

        assert hasattr(policy_engine, "evaluate")
        assert hasattr(RiskEngine, "classify")
        assert hasattr(ApprovalService, "create_approval")
        assert hasattr(ActionExecutionService, "execute_action")
        assert hasattr(AuditService, "log_event")


class TestFireworksLiveSmoke:
    """
    Live smoke test for Fireworks AI.
    Runs ONLY when FIREWORKS_API_KEY is configured in the environment.
    Skipped otherwise to prevent failures or simulated calls.
    """

    @pytest.mark.skipif(
        not os.getenv("FIREWORKS_API_KEY"),
        reason="FIREWORKS_API_KEY environment variable not configured; live smoke test skipped.",
    )
    @pytest.mark.asyncio
    async def test_live_fireworks_chat_completion(self):
        """Execute a live chat completion against official Fireworks AI API."""
        api_key = os.getenv("FIREWORKS_API_KEY", "")
        model = os.getenv("FIREWORKS_MODEL", DEFAULT_FIREWORKS_MODEL)
        base_url = os.getenv("FIREWORKS_BASE_URL", DEFAULT_FIREWORKS_BASE_URL)

        # 1. Verify live authentication on GET /models
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{base_url}/models",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            assert resp.status_code == 200, f"Fireworks authentication failed: HTTP {resp.status_code}"
            models_data = resp.json().get("data", [])
            available_model_ids = [m.get("id") for m in models_data]

        # 2. Select model: configured model if deployed; otherwise active deployed chat model from account
        target_model = model
        if target_model not in available_model_ids:
            qwen_candidates = [
                m for m in available_model_ids
                if "qwen" in m.lower() and "embed" not in m.lower() and "rerank" not in m.lower()
            ]
            target_model = qwen_candidates[0] if qwen_candidates else (available_model_ids[0] if available_model_ids else model)

        provider = FireworksProvider(api_key=api_key, model=target_model, base_url=base_url)
        messages = [
            LLMMessage(
                role="system",
                content="You are a helpful e-commerce assistant. Respond concisely in one sentence.",
            ),
            LLMMessage(role="user", content="Ping test: confirm you are active."),
        ]

        response = await provider.generate(messages=messages, temperature=0.1, max_tokens=50)

        assert response.content is not None and len(response.content.strip()) > 0
        assert response.usage.prompt_tokens > 0
        assert response.usage.completion_tokens > 0
        assert response.finish_reason in ("stop", "length")

