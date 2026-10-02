"""
Flowmint AI — Action Plan API Endpoints (Phase 2B).

Allows merchants to inspect proposed action plans produced by Growth and Recovery agents.
All action plans are PROPOSED in Phase 2B (no execution).
Enforces tenant isolation.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user
from app.core.exceptions import NotFoundError
from app.database import get_db
from app.models.opportunity import ActionPlan
from app.schemas.common import ApiResponse
from app.schemas.opportunity import ActionPlanResponse

router = APIRouter(prefix="/action-plans", tags=["Action Plans"])


@router.get("", response_model=ApiResponse[list[ActionPlanResponse]])
async def list_action_plans(
    status_filter: str | None = Query(default=None, alias="status"),
    action_type: str | None = Query(default=None, alias="type"),
    limit: int = Query(default=20, ge=1, le=100),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List proposed action plans formulated by AI agents for this merchant."""
    query = (
        select(ActionPlan)
        .where(ActionPlan.merchant_id == user.merchant_id)
        .order_by(ActionPlan.created_at.desc())
        .limit(limit)
    )
    if status_filter:
        query = query.where(ActionPlan.status == status_filter.lower())
    if action_type:
        query = query.where(ActionPlan.action_type == action_type.lower())

    res = await db.execute(query)
    plans = res.scalars().all()
    return ApiResponse.ok([ActionPlanResponse.model_validate(p) for p in plans])


@router.get("/{plan_id}", response_model=ApiResponse[ActionPlanResponse])
async def get_action_plan(
    plan_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve details of a specific action plan."""
    query = select(ActionPlan).where(
        ActionPlan.id == plan_id,
        ActionPlan.merchant_id == user.merchant_id,
    )
    res = await db.execute(query)
    plan = res.scalar_one_or_none()
    if not plan:
        raise NotFoundError("ActionPlan", str(plan_id))

    return ApiResponse.ok(ActionPlanResponse.model_validate(plan))
