"""
Flowmint AI — Revenue Attribution API Endpoints (Phase 4).
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user
from app.database import get_db
from app.schemas.attribution import (
    ActionOutcomeResponse,
    AttributionMeasureRequest,
    BeforeVsAfterReportResponse,
)
from app.schemas.common import ApiResponse
from app.services.attribution_service import AttributionService

router = APIRouter(prefix="/attribution", tags=["Attribution"])


@router.get("", response_model=ApiResponse[list[ActionOutcomeResponse]])
@router.get("/outcomes", response_model=ApiResponse[list[ActionOutcomeResponse]])
async def list_outcomes(
    limit: int = Query(default=50, ge=1, le=100),
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    outcomes = await AttributionService.get_outcomes_for_merchant(
        db, current_user.merchant_id, limit=limit
    )
    return ApiResponse.ok([ActionOutcomeResponse.model_validate(o) for o in outcomes])


@router.get("/before-vs-after", response_model=ApiResponse[dict[str, Any] | None])
async def get_general_before_vs_after(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    outcomes = await AttributionService.get_outcomes_for_merchant(db, current_user.merchant_id, limit=1)
    if outcomes:
        outcome = outcomes[0]
        report = await AttributionService.get_before_vs_after_report(db, current_user.merchant_id, outcome.action_id)
        affected = outcome.affected_entities or {}
        cart_ids = affected.get("cart_ids") or affected.get("entities") or []
        eligible_count = len(cart_ids) if isinstance(cart_ids, list) and cart_ids else int(affected.get("count", 0)) or (outcome.orders_attributed or 0)
        conversion_rate = (
            float(outcome.orders_attributed) / eligible_count
            if eligible_count > 0 and outcome.orders_attributed
            else 0.0
        )
        return ApiResponse.ok({
            "campaign_name": report.get("title") or "Revenue Action Recovery",
            "action_id": str(outcome.action_id),
            "trace_id": outcome.trace_id,
            "baseline_window": "Prior 7-Day Baseline",
            "observation_window": "Execution + 24h Window",
            "eligible_entities_count": eligible_count,
            "actual_conversions_count": outcome.orders_attributed,
            "conversion_rate": conversion_rate,
            "observed_gross_revenue": float(outcome.gross_revenue),
            "discount_cost": float(outcome.discount_cost),
            "operational_cost": float(outcome.operational_cost),
            "observed_net_revenue_impact": float(outcome.net_revenue_impact),
            "label": outcome.label,
            "attribution_method": outcome.attribution_method,
            "confidence": float(outcome.confidence),
        })
    return ApiResponse.ok(None)


@router.get("/{action_id}", response_model=ApiResponse[ActionOutcomeResponse | None])
async def get_outcome(
    action_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    outcome = await AttributionService.get_outcome_by_action_id(
        db, current_user.merchant_id, action_id
    )
    if not outcome:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Outcome for action {action_id} not found",
        )
    return ApiResponse.ok(ActionOutcomeResponse.model_validate(outcome))


@router.get("/{action_id}/report", response_model=ApiResponse[BeforeVsAfterReportResponse])
async def get_before_vs_after_report(
    action_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        report = await AttributionService.get_before_vs_after_report(
            db, current_user.merchant_id, action_id
        )
        return ApiResponse.ok(BeforeVsAfterReportResponse.model_validate(report))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/measure", response_model=ApiResponse[ActionOutcomeResponse])
async def measure_outcome(
    req: AttributionMeasureRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        outcome = await AttributionService.record_outcome_for_execution(
            db=db,
            merchant_id=current_user.merchant_id,
            action_plan_id=req.action_id,
            attribution_method=req.attribution_method,
            label=req.label,
            custom_metrics=req.custom_metrics,
        )
        return ApiResponse.ok(ActionOutcomeResponse.model_validate(outcome))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
