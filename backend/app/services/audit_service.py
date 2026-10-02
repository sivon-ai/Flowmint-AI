"""
Flowmint AI — Audit Trail Service (Phase 3).

Provides append-only, immutable recording of all governance, policy, approval,
and action execution events.
Audit logs cannot be modified or deleted through application APIs.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.governance import AuditLog


class AuditService:
    """
    Immutable audit logging service.
    """

    @staticmethod
    async def log_event(
        db: AsyncSession,
        merchant_id: uuid.UUID,
        actor_type: str,  # "agent", "user", "system"
        actor_id: str,
        event_type: str,  # "action.proposed", "policy.evaluated", "approval.requested", "approval.decided", "action.executed", "action.blocked"
        reason: str,
        action_id: uuid.UUID | None = None,
        agent: str | None = None,
        previous_status: str | None = None,
        new_status: str | None = None,
        policy_results: dict[str, Any] | None = None,
        approval_result: dict[str, Any] | None = None,
        execution_result: dict[str, Any] | None = None,
        trace_id: str | None = None,
    ) -> AuditLog:
        event_id = f"evt_{uuid.uuid4().hex[:16]}"
        entry = AuditLog(
            merchant_id=merchant_id,
            event_id=event_id,
            actor_type=actor_type,
            actor_id=actor_id,
            action_id=action_id,
            agent=agent,
            event_type=event_type,
            previous_status=previous_status,
            new_status=new_status,
            reason=reason,
            policy_results=policy_results or {},
            approval_result=approval_result or {},
            execution_result=execution_result or {},
            trace_id=trace_id or f"trc_{uuid.uuid4().hex[:12]}",
            created_at=datetime.now(timezone.utc),
        )
        db.add(entry)
        await db.flush()
        return entry

    @staticmethod
    async def list_logs(
        db: AsyncSession,
        merchant_id: uuid.UUID,
        action_id: uuid.UUID | None = None,
        event_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[AuditLog]:
        stmt = (
            select(AuditLog)
            .where(AuditLog.merchant_id == merchant_id)
            .order_by(desc(AuditLog.created_at))
            .limit(limit)
            .offset(offset)
        )
        if action_id:
            stmt = stmt.where(AuditLog.action_id == action_id)
        if event_type:
            stmt = stmt.where(AuditLog.event_type == event_type)

        res = await db.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def get_log(db: AsyncSession, merchant_id: uuid.UUID, log_id: uuid.UUID) -> AuditLog | None:
        stmt = select(AuditLog).where(
            AuditLog.id == log_id,
            AuditLog.merchant_id == merchant_id,
        )
        res = await db.execute(stmt)
        return res.scalar_one_or_none()
