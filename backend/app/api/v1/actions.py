"""
Flowmint AI — Action Lifecycle, Validation, and Controlled Execution Endpoints (Phase 3).
"""

from __future__ import annotations

import uuid
from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.exceptions import NotFoundError
from app.database import get_db
from app.models.opportunity import ActionPlan
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.governance import ActionExecuteRequest, ActionExecuteResponse
from app.schemas.opportunity import ActionPlanResponse
from app.services.action_execution_service import ActionExecutionService

router = APIRouter(prefix="/actions", tags=["Action Execution & Governance"])


@router.get("", response_model=ApiResponse[list[ActionPlanResponse]])
async def list_actions(
    status: str | None = Query(None, description="Filter by action status"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Lists action plans for the current authenticated merchant."""
    stmt = (
        select(ActionPlan)
        .where(ActionPlan.merchant_id == current_user.merchant_id)
        .order_by(desc(ActionPlan.created_at))
    )
    if status:
        stmt = stmt.where(ActionPlan.status == status)

    res = await db.execute(stmt)
    plans = res.scalars().all()

    return ApiResponse.ok(
        [
            ActionPlanResponse(
                id=p.id,
                action_id=f"act_{p.id.hex[:12]}",
                merchant_id=p.merchant_id,
                opportunity_id=p.opportunity_id,
                action_type=p.action_type,
                target=p.target,
                parameters=p.parameters,
                evidence=p.evidence,
                recommendation_reason=p.recommendation_reason,
                estimated_impact=p.estimated_impact,
                risk_level=p.risk_level,
                requires_approval=p.requires_approval,
                status=p.status,
                created_at=p.created_at,
            )
            for p in plans
        ]
    )


@router.get("/{action_id}", response_model=ApiResponse[ActionPlanResponse])
async def get_action(
    action_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieves details of a specific action plan."""
    stmt = select(ActionPlan).where(
        ActionPlan.id == action_id,
        ActionPlan.merchant_id == current_user.merchant_id,
    )
    res = await db.execute(stmt)
    p = res.scalar_one_or_none()
    if not p:
        raise NotFoundError(f"Action plan '{action_id}' not found")

    return ApiResponse.ok(
        ActionPlanResponse(
            id=p.id,
            action_id=f"act_{p.id.hex[:12]}",
            merchant_id=p.merchant_id,
            opportunity_id=p.opportunity_id,
            action_type=p.action_type,
            target=p.target,
            parameters=p.parameters,
            evidence=p.evidence,
            recommendation_reason=p.recommendation_reason,
            estimated_impact=p.estimated_impact,
            risk_level=p.risk_level,
            requires_approval=p.requires_approval,
            status=p.status,
            created_at=p.created_at,
        )
    )


@router.post("/{action_id}/validate", response_model=ApiResponse[dict])
async def validate_action(
    action_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Validates an ActionPlan against agent permissions and deterministic policy rules.
    If approval is required, transitions to PENDING_APPROVAL and generates an Approval record.
    Does NOT execute write tools.
    """
    validation_result = await ActionExecutionService.validate_action(
        db=db,
        merchant_id=current_user.merchant_id,
        action_plan_id=action_id,
    )
    await db.commit()
    return ApiResponse.ok(validation_result)


@router.post("/{action_id}/execute", response_model=ApiResponse[ActionExecuteResponse])
async def execute_action(
    action_id: uuid.UUID,
    body: ActionExecuteRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Executes a validated, approved ActionPlan via controlled write tools.
    Enforces permission, policy, risk, approval, and idempotency invariants.
    """
    result = await ActionExecutionService.execute_action(
        db=db,
        merchant_id=current_user.merchant_id,
        action_plan_id=action_id,
        idempotency_key=body.idempotency_key,
        user_id=current_user.id,
    )
    await db.commit()
    return ApiResponse.ok(
        ActionExecuteResponse(
            status=result["status"],
            idempotent_replay=result["idempotent_replay"],
            execution_id=result["execution_id"],
            action_id=result["action_id"],
            tool_name=result["tool_name"],
            result=result["result"],
            message=result["message"],
        )
    )
