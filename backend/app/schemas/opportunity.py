"""
Flowmint AI — Opportunity and ActionPlan Pydantic Schemas (Phase 2B).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class OpportunityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    merchant_id: uuid.UUID
    type: str
    title: str
    description: str
    status: str
    priority: str
    confidence: float
    estimated_value: float
    currency: str
    evidence_json: dict[str, Any] = Field(validation_alias="evidence_json", serialization_alias="evidence")
    affected_entity_type: str
    affected_entity_ids: list[Any]
    recommended_action: str | None = None
    detected_at: datetime
    expires_at: datetime | None = None
    resolved_at: datetime | None = None
    created_at: datetime


class ActionPlanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    merchant_id: uuid.UUID
    opportunity_id: uuid.UUID | None = None
    action_type: str
    target: str
    parameters: dict[str, Any]
    evidence: dict[str, Any]
    recommendation_reason: str
    estimated_impact: dict[str, Any]
    risk_level: str
    requires_approval: bool
    status: str
    created_at: datetime


class OpportunityDetailResponse(BaseModel):
    opportunity: OpportunityResponse
    action_plans: list[ActionPlanResponse] = Field(default_factory=list)
    simulations: list[dict[str, Any]] = Field(default_factory=list)


class OpportunityInvestigateResponse(BaseModel):
    opportunity_id: str
    type: str
    title: str
    status: str
    priority: str
    estimated_value: float
    evidence: dict[str, Any]
    recommended_action: str | None = None
    actionable_records: list[Any] = Field(default_factory=list)
    investigation_notes: list[str] = Field(default_factory=list)


class RevenueOverviewMetricsResponse(BaseModel):
    period_days: int
    total_revenue: float
    paid_orders: int
    completed_orders: int | None = None
    average_order_value: float
    aov: float | None = None
    total_carts: int
    abandoned_cart_count: int
    abandoned_cart_value: float
    abandonment_rate: float
    cart_abandonment_rate: float | None = None
    conversion_rate: float
    checkout_conversion_rate: float | None = None
    total_payments: int
    failed_payment_count: int
    failed_payment_value: float
    payment_failure_rate: float
    revenue_at_risk: float
    active_opportunities_count: int | None = 0
    inventory_pressure: dict[str, int]
