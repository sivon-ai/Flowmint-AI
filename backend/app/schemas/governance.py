"""
Flowmint AI — Governance, Policy, Approval & Execution Pydantic Schemas (Phase 3).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


# ----------------------------------------------------
# Policy Schemas
# ----------------------------------------------------

class PolicyEvaluateRequest(BaseModel):
    action_plan_id: uuid.UUID | None = None
    action_type: str = Field(..., description="Action type to test: cross_sell_bundle, promotional_offer, abandoned_cart_recovery")
    target: str = Field("test_target", description="Target identifier or criteria")
    parameters: dict[str, Any] = Field(default_factory=dict, description="Action parameters (e.g. discount_percentage, budget)")
    agent_name: str = Field("growth_agent", description="Proposing agent name")


class PolicyRuleResultSchema(BaseModel):
    rule: str
    passed: bool
    severity: str
    reason: str
    evidence: dict[str, Any] = Field(default_factory=dict)


class PolicyEvaluateResponse(BaseModel):
    allowed: bool
    requires_approval: bool
    risk_level: str
    reasons: list[str]
    rule_results: list[PolicyRuleResultSchema]
    evidence_snapshot: dict[str, Any] = Field(default_factory=dict)


class MerchantPolicyResponse(BaseModel):
    id: uuid.UUID
    merchant_id: uuid.UUID
    max_discount_percentage: float
    max_campaign_budget: float
    high_value_threshold: float
    contact_cooldown_hours: int
    require_approval_all_actions: bool
    auto_approval_max_risk: str
    allowed_action_types: list[str]
    restricted_product_ids: list[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime


class MerchantPolicyUpdateRequest(BaseModel):
    max_discount_percentage: float | None = Field(None, ge=1.0, le=50.0)
    max_campaign_budget: float | None = Field(None, ge=0.0)
    high_value_threshold: float | None = Field(None, ge=0.0)
    contact_cooldown_hours: int | None = Field(None, ge=1, le=168)
    require_approval_all_actions: bool | None = None
    allowed_action_types: list[str] | None = None
    restricted_product_ids: list[str] | None = None


# ----------------------------------------------------
# Approval Schemas
# ----------------------------------------------------

class ApprovalResponse(BaseModel):
    id: uuid.UUID
    merchant_id: uuid.UUID
    action_plan_id: uuid.UUID
    requested_by: str
    risk_level: str
    reason: str
    status: str
    expires_at: datetime
    decided_at: datetime | None = None
    decided_by: uuid.UUID | None = None
    decision_reason: str | None = None
    policy_snapshot: dict[str, Any] = Field(default_factory=dict)
    action_plan: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


class ApprovalDecisionRequest(BaseModel):
    decision_reason: str = Field(..., min_length=2, description="Reason for approving or rejecting")


# ----------------------------------------------------
# Execution Schemas
# ----------------------------------------------------

class ActionExecuteRequest(BaseModel):
    idempotency_key: str = Field(..., description="Unique client-supplied idempotency key")


class ActionExecuteResponse(BaseModel):
    status: str
    idempotent_replay: bool
    execution_id: str
    action_id: str
    tool_name: str
    result: dict[str, Any]
    message: str


# ----------------------------------------------------
# Audit Schemas
# ----------------------------------------------------

class AuditLogResponse(BaseModel):
    id: uuid.UUID
    merchant_id: uuid.UUID
    event_id: str
    actor_type: str
    actor_id: str
    action_id: uuid.UUID | None = None
    agent: str | None = None
    event_type: str
    previous_status: str | None = None
    new_status: str | None = None
    reason: str
    policy_results: dict[str, Any] | None = None
    approval_result: dict[str, Any] | None = None
    execution_result: dict[str, Any] | None = None
    trace_id: str | None = None
    created_at: datetime
