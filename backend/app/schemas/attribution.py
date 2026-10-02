"""
Flowmint AI — Pydantic Schemas for Phase 4 (Attribution, Evaluation, Trace, Performance).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ActionOutcomeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    merchant_id: uuid.UUID
    action_id: uuid.UUID
    execution_id: uuid.UUID | None = None
    opportunity_id: uuid.UUID | None = None
    trace_id: str | None = None
    label: str
    attribution_method: str
    confidence: Decimal
    baseline_period: dict[str, Any]
    observation_period: dict[str, Any]
    affected_entities: dict[str, Any]
    orders_attributed: int
    gross_revenue: Decimal
    discount_cost: Decimal
    operational_cost: Decimal
    net_revenue_impact: Decimal
    evidence_summary: str | None = None
    observed_at: datetime
    created_at: datetime


class BeforeVsAfterReportResponse(BaseModel):
    action_id: str
    action_type: str
    title: str
    status: str
    before_action: dict[str, Any]
    after_action: dict[str, Any]
    disclaimer: str


class AttributionMeasureRequest(BaseModel):
    action_id: uuid.UUID
    attribution_method: str = "deterministic_event"
    label: str = "OBSERVED"
    custom_metrics: dict[str, Any] | None = None


class EvaluationBenchmarkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: uuid.UUID
    runner_type: str
    model_name: str
    dataset_version: str
    total_cases: int
    passed_cases: int
    intent_accuracy: Decimal
    tool_accuracy: Decimal
    param_accuracy: Decimal
    grounding_rate: Decimal
    hallucination_rate: Decimal
    safety_pass_rate: Decimal
    injection_resistance_rate: Decimal
    avg_latency_ms: int
    total_tokens: int
    estimated_cost_usd: Decimal
    results_breakdown: dict[str, Any]
    created_at: datetime


class BenchmarkRunRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    runner_type: str = "mock_llm"
    model_name: str | None = None


class TraceNode(BaseModel):
    step: int
    sub_step: int | None = None
    type: str
    label: str
    status: str
    timestamp: str
    latency_ms: int | None = None
    tokens: int | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class TraceResponse(BaseModel):
    trace_id: str
    merchant_id: str
    total_nodes: int
    timeline: list[TraceNode]


class PerformanceMetricsResponse(BaseModel):
    api_latency_p50_ms: int
    api_latency_p95_ms: int
    agent_latency_avg_ms: int
    tool_latency_avg_ms: int
    db_latency_avg_ms: int
    max_tool_calls_budget: int
    max_token_budget: int
    pricing_rates: dict[str, float]
