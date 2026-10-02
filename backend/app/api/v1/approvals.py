"""
Flowmint AI — Approval Workflow Endpoints (Phase 3).
"""

from __future__ import annotations

import uuid
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.exceptions import NotFoundError
from app.database import get_db
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.governance import ApprovalDecisionRequest, ApprovalResponse
from app.services.approval_service import ApprovalService

router = APIRouter(prefix="/approvals", tags=["Human Approvals"])


@router.get("", response_model=ApiResponse[list[ApprovalResponse]])
async def list_approvals(
    status: str | None = Query(None, description="Filter by approval status (pending, approved, rejected, expired)"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Lists approval requests for the current merchant."""
    approvals = await ApprovalService.list_approvals(
        db=db,
        merchant_id=current_user.merchant_id,
        status=status,
    )
    return ApiResponse.ok(
        [
            ApprovalResponse(
                id=a.id,
                merchant_id=a.merchant_id,
                action_plan_id=a.action_plan_id,
                requested_by=a.requested_by,
                risk_level=a.risk_level,
                reason=a.reason,
                status=a.status,
                expires_at=a.expires_at,
                decided_at=a.decided_at,
                decided_by=a.decided_by,
                decision_reason=a.decision_reason,
                policy_snapshot=a.policy_snapshot,
                action_plan={
                    "id": str(a.action_plan.id),
                    "action_type": a.action_plan.action_type,
                    "target": a.action_plan.target,
                    "parameters": a.action_plan.parameters,
                    "estimated_impact": a.action_plan.estimated_impact,
                    "status": a.action_plan.status,
                }
                if a.action_plan
                else None,
                created_at=a.created_at,
                updated_at=a.updated_at,
            )
            for a in approvals
        ]
    )


@router.get("/{approval_id}", response_model=ApiResponse[ApprovalResponse])
async def get_approval(
    approval_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieves details of an individual approval request."""
    a = await ApprovalService.get_approval(
        db=db,
        merchant_id=current_user.merchant_id,
        approval_id=approval_id,
    )
    if not a:
        raise NotFoundError(f"Approval '{approval_id}' not found")

    return ApiResponse.ok(
        ApprovalResponse(
            id=a.id,
            merchant_id=a.merchant_id,
            action_plan_id=a.action_plan_id,
            requested_by=a.requested_by,
            risk_level=a.risk_level,
            reason=a.reason,
            status=a.status,
            expires_at=a.expires_at,
            decided_at=a.decided_at,
            decided_by=a.decided_by,
            decision_reason=a.decision_reason,
            policy_snapshot=a.policy_snapshot,
            action_plan={
                "id": str(a.action_plan.id),
                "action_type": a.action_plan.action_type,
                "target": a.action_plan.target,
                "parameters": a.action_plan.parameters,
                "estimated_impact": a.action_plan.estimated_impact,
                "status": a.action_plan.status,
            }
            if a.action_plan
            else None,
            created_at=a.created_at,
            updated_at=a.updated_at,
        )
    )


@router.post("/{approval_id}/approve", response_model=ApiResponse[ApprovalResponse])
async def approve_action(
    approval_id: uuid.UUID,
    body: ApprovalDecisionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Merchant approves the pending ActionPlan."""
    approval, _ = await ApprovalService.decide_approval(
        db=db,
        approval_id=approval_id,
        merchant_id=current_user.merchant_id,
        decided_by=current_user.id,
        approved=True,
        decision_reason=body.decision_reason,
    )
    await db.commit()
    await db.refresh(approval)

    return ApiResponse.ok(
        ApprovalResponse(
            id=approval.id,
            merchant_id=approval.merchant_id,
            action_plan_id=approval.action_plan_id,
            requested_by=approval.requested_by,
            risk_level=approval.risk_level,
            reason=approval.reason,
            status=approval.status,
            expires_at=approval.expires_at,
            decided_at=approval.decided_at,
            decided_by=approval.decided_by,
            decision_reason=approval.decision_reason,
            policy_snapshot=approval.policy_snapshot,
            action_plan=None,
            created_at=approval.created_at,
            updated_at=approval.updated_at,
        )
    )


@router.post("/{approval_id}/reject", response_model=ApiResponse[ApprovalResponse])
async def reject_action(
    approval_id: uuid.UUID,
    body: ApprovalDecisionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Merchant rejects the pending ActionPlan."""
    approval, _ = await ApprovalService.decide_approval(
        db=db,
        approval_id=approval_id,
        merchant_id=current_user.merchant_id,
        decided_by=current_user.id,
        approved=False,
        decision_reason=body.decision_reason,
    )
    await db.commit()
    await db.refresh(approval)

    return ApiResponse.ok(
        ApprovalResponse(
            id=approval.id,
            merchant_id=approval.merchant_id,
            action_plan_id=approval.action_plan_id,
            requested_by=approval.requested_by,
            risk_level=approval.risk_level,
            reason=approval.reason,
            status=approval.status,
            expires_at=approval.expires_at,
            decided_at=approval.decided_at,
            decided_by=approval.decided_by,
            decision_reason=approval.decision_reason,
            policy_snapshot=approval.policy_snapshot,
            action_plan=None,
            created_at=approval.created_at,
            updated_at=approval.updated_at,
        )
    )
