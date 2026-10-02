"""
Flowmint AI — Audit Trail Endpoints (Phase 3).
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
from app.schemas.governance import AuditLogResponse
from app.services.audit_service import AuditService

router = APIRouter(prefix="/audit", tags=["Audit Trail"])


@router.get("", response_model=ApiResponse[list[AuditLogResponse]])
async def list_audit_logs(
    action_id: uuid.UUID | None = Query(None, description="Filter by action plan UUID"),
    event_type: str | None = Query(None, description="Filter by event type"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Lists immutable audit log entries for current merchant."""
    logs = await AuditService.list_logs(
        db=db,
        merchant_id=current_user.merchant_id,
        action_id=action_id,
        event_type=event_type,
        limit=limit,
        offset=offset,
    )
    return ApiResponse.ok(
        [
            AuditLogResponse(
                id=log.id,
                merchant_id=log.merchant_id,
                event_id=log.event_id,
                actor_type=log.actor_type,
                actor_id=log.actor_id,
                action_id=log.action_id,
                agent=log.agent,
                event_type=log.event_type,
                previous_status=log.previous_status,
                new_status=log.new_status,
                reason=log.reason,
                policy_results=log.policy_results,
                approval_result=log.approval_result,
                execution_result=log.execution_result,
                trace_id=log.trace_id,
                created_at=log.created_at,
            )
            for log in logs
        ]
    )


@router.get("/{log_id}", response_model=ApiResponse[AuditLogResponse])
async def get_audit_log(
    log_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieves an individual immutable audit log entry."""
    log = await AuditService.get_log(
        db=db,
        merchant_id=current_user.merchant_id,
        log_id=log_id,
    )
    if not log:
        raise NotFoundError(f"Audit log entry '{log_id}' not found")

    return ApiResponse.ok(
        AuditLogResponse(
            id=log.id,
            merchant_id=log.merchant_id,
            event_id=log.event_id,
            actor_type=log.actor_type,
            actor_id=log.actor_id,
            action_id=log.action_id,
            agent=log.agent,
            event_type=log.event_type,
            previous_status=log.previous_status,
            new_status=log.new_status,
            reason=log.reason,
            policy_results=log.policy_results,
            approval_result=log.approval_result,
            execution_result=log.execution_result,
            trace_id=log.trace_id,
            created_at=log.created_at,
        )
    )
