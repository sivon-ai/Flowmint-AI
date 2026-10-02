"""
Flowmint AI — Approval Workflow Service (Phase 3).

Manages human-in-the-loop decisions for bounded revenue actions.
Enforces multi-tenant isolation, decision auditability, and expiration windows.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundError, ValidationError
from app.models.governance import Approval, ApprovalStatus
from app.models.opportunity import ActionPlan, ActionPlanStatus
from app.services.audit_service import AuditService


class ApprovalService:
    """
    Approval workflow manager.
    """

    @staticmethod
    async def create_approval(
        db: AsyncSession,
        merchant_id: uuid.UUID,
        action_plan_id: uuid.UUID,
        requested_by: str,
        risk_level: str,
        reason: str,
        policy_snapshot: dict[str, Any],
        expires_in_hours: int = 48,
    ) -> Approval:
        # Check if active approval already exists for this action plan
        stmt = select(Approval).where(
            Approval.action_plan_id == action_plan_id,
            Approval.merchant_id == merchant_id,
            Approval.status == ApprovalStatus.PENDING.value,
        )
        res = await db.execute(stmt)
        existing = res.scalar_one_or_none()
        if existing:
            return existing

        expires_at = datetime.now(timezone.utc) + timedelta(hours=expires_in_hours)
        approval = Approval(
            merchant_id=merchant_id,
            action_plan_id=action_plan_id,
            requested_by=requested_by,
            risk_level=risk_level,
            reason=reason,
            status=ApprovalStatus.PENDING.value,
            expires_at=expires_at,
            policy_snapshot=policy_snapshot,
        )
        db.add(approval)
        await db.flush()

        await AuditService.log_event(
            db=db,
            merchant_id=merchant_id,
            actor_type="system",
            actor_id=requested_by,
            action_id=action_plan_id,
            agent=requested_by,
            event_type="approval.requested",
            previous_status=ActionPlanStatus.VALIDATING.value,
            new_status=ActionPlanStatus.PENDING_APPROVAL.value,
            reason=f"Action requires approval due to risk level '{risk_level}' and policy constraints.",
            policy_results=policy_snapshot,
            approval_result={"approval_id": str(approval.id), "status": approval.status},
        )
        return approval

    @staticmethod
    async def decide_approval(
        db: AsyncSession,
        approval_id: uuid.UUID,
        merchant_id: uuid.UUID,
        decided_by: uuid.UUID,
        approved: bool,
        decision_reason: str,
    ) -> tuple[Approval, ActionPlan]:
        stmt = (
            select(Approval)
            .options(selectinload(Approval.action_plan))
            .where(
                Approval.id == approval_id,
                Approval.merchant_id == merchant_id,
            )
        )
        res = await db.execute(stmt)
        approval = res.scalar_one_or_none()
        if not approval:
            raise NotFoundError(f"Approval record '{approval_id}' not found")

        # Expiry check
        now = datetime.now(timezone.utc)
        if approval.status == ApprovalStatus.PENDING.value and approval.expires_at < now:
            approval.status = ApprovalStatus.EXPIRED.value
            await db.flush()
            raise ValidationError("This approval request has expired and cannot be approved.")

        if approval.status != ApprovalStatus.PENDING.value:
            raise ValidationError(f"Approval is already in terminal state '{approval.status}'")

        action_plan = approval.action_plan
        prev_plan_status = action_plan.status

        approval.decided_at = now
        approval.decided_by = decided_by
        approval.decision_reason = decision_reason

        if approved:
            approval.status = ApprovalStatus.APPROVED.value
            action_plan.status = ActionPlanStatus.READY_FOR_REVIEW.value  # ready to be executed
            event_type = "approval.approved"
        else:
            approval.status = ApprovalStatus.REJECTED.value
            action_plan.status = ActionPlanStatus.REJECTED.value
            event_type = "approval.rejected"

        await db.flush()

        await AuditService.log_event(
            db=db,
            merchant_id=merchant_id,
            actor_type="user",
            actor_id=str(decided_by),
            action_id=action_plan.id,
            event_type=event_type,
            previous_status=prev_plan_status,
            new_status=action_plan.status,
            reason=decision_reason or ("Merchant approved action" if approved else "Merchant rejected action"),
            approval_result={
                "approval_id": str(approval.id),
                "decision": approval.status,
                "decided_by": str(decided_by),
            },
        )
        return approval, action_plan

    @staticmethod
    async def list_approvals(
        db: AsyncSession,
        merchant_id: uuid.UUID,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Approval]:
        stmt = (
            select(Approval)
            .options(selectinload(Approval.action_plan))
            .where(Approval.merchant_id == merchant_id)
            .order_by(desc(Approval.created_at))
            .limit(limit)
            .offset(offset)
        )
        if status:
            stmt = stmt.where(Approval.status == status)

        res = await db.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def get_approval(
        db: AsyncSession, merchant_id: uuid.UUID, approval_id: uuid.UUID
    ) -> Approval | None:
        stmt = (
            select(Approval)
            .options(selectinload(Approval.action_plan))
            .where(
                Approval.id == approval_id,
                Approval.merchant_id == merchant_id,
            )
        )
        res = await db.execute(stmt)
        return res.scalar_one_or_none()
