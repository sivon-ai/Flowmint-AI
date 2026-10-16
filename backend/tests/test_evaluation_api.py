"""
Unit and integration tests for Evaluation Benchmark API Endpoints.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.merchant import Merchant


@pytest.mark.asyncio
async def test_get_dataset_info_endpoint(client: AsyncClient, auth_headers: dict):
    """Verifies GET /api/v1/evaluation/dataset returns breakdown and fireworks configuration."""
    res = await client.get("/api/v1/evaluation/dataset", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["total_cases"] == 900
    assert "categories" in data
    assert "fireworks_configured" in data
    assert "fireworks_model" in data


@pytest.mark.asyncio
async def test_run_mock_llm_benchmark(client: AsyncClient, auth_headers: dict):
    """Verifies POST /api/v1/evaluation/run with mock_llm executes the 900-case suite."""
    res = await client.post(
        "/api/v1/evaluation/run",
        headers=auth_headers,
        json={"runner_type": "mock_llm", "model_name": "mock-llm-v1"},
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["id"] is not None
    assert data["runner_type"] == "mock_llm"
    assert data["model_name"] == "mock-llm-v1"
    assert data["total_cases"] == 900
    assert data["passed_cases"] >= 850
    # Numerical units: calculated on 0-100 percentage scale
    assert float(data["intent_accuracy"]) >= 90.0
    assert float(data["tool_accuracy"]) >= 90.0
    assert float(data["safety_pass_rate"]) == 100.0
    assert float(data["injection_resistance_rate"]) == 100.0
    assert int(data["avg_latency_ms"]) > 0
    assert int(data["total_tokens"]) > 0


@pytest.mark.asyncio
async def test_run_real_llm_missing_fireworks_key_fails_cleanly(
    client: AsyncClient, auth_headers: dict, monkeypatch
):
    """Verifies that requesting real_llm evaluation without FIREWORKS_API_KEY returns 400 with honest error."""
    settings = get_settings()
    monkeypatch.setattr(settings, "fireworks_api_key", "")
    monkeypatch.setattr(settings, "openai_api_key", "")
    monkeypatch.setattr(settings, "anthropic_api_key", "")
    monkeypatch.setattr(settings, "google_api_key", "")

    res = await client.post(
        "/api/v1/evaluation/run",
        headers=auth_headers,
        json={"runner_type": "real_llm", "model_name": "accounts/fireworks/models/qwen3p8-max"},
    )
    assert res.status_code == 400
    err_detail = res.json().get("detail", "")
    assert "FIREWORKS_API_KEY" in err_detail or "BLOCKED" in err_detail


@pytest.mark.asyncio
async def test_list_benchmarks_endpoint(client: AsyncClient, auth_headers: dict):
    """Verifies GET /api/v1/evaluation/benchmarks retrieves recorded benchmark runs."""
    res = await client.get("/api/v1/evaluation/benchmarks", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()["data"]
    assert isinstance(data, list)
    if len(data) > 0:
        bm = data[0]
        assert "id" in bm
        assert "runner_type" in bm
        assert "model_name" in bm
        assert "intent_accuracy" in bm
        assert "tool_accuracy" in bm
        assert "param_accuracy" in bm
