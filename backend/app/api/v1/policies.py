"""
Flowmint AI — Policy Simulator and Configuration Endpoints (Phase 3).
"""

from __future__ import annotations

from decimal import Decimal
import uuid
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.governance import MerchantPolicy
from app.models.opportunity import ActionPlan
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.governance import (
    MerchantPolicyResponse,
    MerchantPolicyUpdateRequest,
    PolicyEvaluateRequest,
    PolicyEvaluateResponse,
)
from app.services.policy_engine import PolicyContext, policy_engine

router = APIRouter(prefix="/policies", tags=["Policies & Governance"])


@router.post("/evaluate", response_model=ApiResponse[PolicyEvaluateResponse])
async def evaluate_policy(
    body: PolicyEvaluateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Policy Simulator Endpoint:
    Evaluates an ActionPlan or proposed parameters against all policy rules.
    Does NOT execute any write actions.
    """
    # Load merchant policy
    stmt = select(MerchantPolicy).where(
        MerchantPolicy.merchant_id == current_user.merchant_id,
        MerchantPolicy.is_active == True,
    )
    res = await db.execute(stmt)
    policy = res.scalar_one_or_none()

    if body.action_plan_id:
        plan_stmt = select(ActionPlan).where(
            ActionPlan.id == body.action_plan_id,
            ActionPlan.merchant_id == current_user.merchant_id,
        )
        plan_res = await db.execute(plan_stmt)
        plan = plan_res.scalar_one_or_none()
        if not plan:
            plan = ActionPlan(
                merchant_id=current_user.merchant_id,
                action_type=body.action_type,
                target=body.target,
                parameters=body.parameters,
                evidence={},
                recommendation_reason="Simulated policy check",
            )
    else:
        plan = ActionPlan(
            merchant_id=current_user.merchant_id,
            action_type=body.action_type,
            target=body.target,
            parameters=body.parameters,
            evidence={},
            recommendation_reason="Simulated policy check",
        )

    context = PolicyContext(
        merchant_id=current_user.merchant_id,
        db=db,
        policy=policy,
        agent_name=body.agent_name,
    )

    evaluation = await policy_engine.evaluate(plan, context)

    response_data = PolicyEvaluateResponse(
        allowed=evaluation.allowed,
        requires_approval=evaluation.requires_approval,
        risk_level=evaluation.risk_level,
        reasons=evaluation.reasons,
        rule_results=[
            {
                "rule": r.rule,
                "passed": r.passed,
                "severity": r.severity,
                "reason": r.reason,
                "evidence": r.evidence,
            }
            for r in evaluation.rule_results
        ],
        evidence_snapshot=evaluation.evidence_snapshot,
    )
    return ApiResponse.ok(response_data)


@router.get("", response_model=ApiResponse[MerchantPolicyResponse])
async def get_merchant_policy(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieves or auto-creates the merchant policy configuration."""
    stmt = select(MerchantPolicy).where(
        MerchantPolicy.merchant_id == current_user.merchant_id
    )
    res = await db.execute(stmt)
    policy = res.scalar_one_or_none()

    if not policy:
        policy = MerchantPolicy(merchant_id=current_user.merchant_id)
        db.add(policy)
        await db.commit()
        await db.refresh(policy)

    return ApiResponse.ok(
        MerchantPolicyResponse(
            id=policy.id,
            merchant_id=policy.merchant_id,
            max_discount_percentage=float(policy.max_discount_percentage),
            max_campaign_budget=float(policy.max_campaign_budget),
            high_value_threshold=float(policy.high_value_threshold),
            contact_cooldown_hours=policy.contact_cooldown_hours,
            require_approval_all_actions=policy.require_approval_all_actions,
            auto_approval_max_risk=policy.auto_approval_max_risk,
            allowed_action_types=policy.allowed_action_types,
            restricted_product_ids=policy.restricted_product_ids,
            is_active=policy.is_active,
            created_at=policy.created_at,
            updated_at=policy.updated_at,
        )
    )


@router.put("", response_model=ApiResponse[MerchantPolicyResponse])
async def update_merchant_policy(
    body: MerchantPolicyUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Updates the merchant policy configuration."""
    stmt = select(MerchantPolicy).where(
        MerchantPolicy.merchant_id == current_user.merchant_id
    )
    res = await db.execute(stmt)
    policy = res.scalar_one_or_none()

    if not policy:
        policy = MerchantPolicy(merchant_id=current_user.merchant_id)
        db.add(policy)

    if body.max_discount_percentage is not None:
        policy.max_discount_percentage = Decimal(str(body.max_discount_percentage))
    if body.max_campaign_budget is not None:
        policy.max_campaign_budget = Decimal(str(body.max_campaign_budget))
    if body.high_value_threshold is not None:
        policy.high_value_threshold = Decimal(str(body.high_value_threshold))
    if body.contact_cooldown_hours is not None:
        policy.contact_cooldown_hours = body.contact_cooldown_hours
    if body.require_approval_all_actions is not None:
        policy.require_approval_all_actions = body.require_approval_all_actions
    if body.allowed_action_types is not None:
        policy.allowed_action_types = body.allowed_action_types
    if body.restricted_product_ids is not None:
        policy.restricted_product_ids = body.restricted_product_ids

    await db.commit()
    await db.refresh(policy)

    return ApiResponse.ok(
        MerchantPolicyResponse(
            id=policy.id,
            merchant_id=policy.merchant_id,
            max_discount_percentage=float(policy.max_discount_percentage),
            max_campaign_budget=float(policy.max_campaign_budget),
            high_value_threshold=float(policy.high_value_threshold),
            contact_cooldown_hours=policy.contact_cooldown_hours,
            require_approval_all_actions=policy.require_approval_all_actions,
            auto_approval_max_risk=policy.auto_approval_max_risk,
            allowed_action_types=policy.allowed_action_types,
            restricted_product_ids=policy.restricted_product_ids,
            is_active=policy.is_active,
            created_at=policy.created_at,
            updated_at=policy.updated_at,
        )
    )
