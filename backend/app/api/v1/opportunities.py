"""
Flowmint AI — Opportunity API Endpoints (Phase 2B).

Exposes revenue opportunities, automated detection, deep-dive investigations,
and real-time revenue at risk indicators.
Enforces strict merchant ownership and tenant isolation.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, get_current_user
from app.core.exceptions import NotFoundError
from app.database import get_db
from app.models.opportunity import ActionPlan, Opportunity, OpportunityStatus, SimulationRecord
from app.schemas.common import ApiResponse
from app.schemas.opportunity import (
    ActionPlanResponse,
    OpportunityDetailResponse,
    OpportunityInvestigateResponse,
    OpportunityResponse,
    RevenueOverviewMetricsResponse,
)
from app.services.opportunity_engine import OpportunityEngine
from app.services.revenue_intelligence import RevenueIntelligenceService

router = APIRouter(prefix="/opportunities", tags=["Revenue Opportunities"])


@router.get("/metrics/overview", response_model=ApiResponse[RevenueOverviewMetricsResponse])
async def get_revenue_overview(
    days: int = Query(default=30, ge=1, le=365),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Returns top-level revenue, risk, conversion, and inventory pressure metrics."""
    metrics = await RevenueIntelligenceService.get_overview_metrics(
        db=db, merchant_id=user.merchant_id, days=days
    )
    return ApiResponse.ok(RevenueOverviewMetricsResponse.model_validate(metrics))


@router.get("", response_model=ApiResponse[list[OpportunityResponse]])
async def list_opportunities(
    status_filter: str | None = Query(default=None, alias="status"),
    type_filter: str | None = Query(default=None, alias="type"),
    auto_detect: bool = Query(default=True, description="Automatically run detectors if none exist"),
    limit: int = Query(default=20, ge=1, le=100),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List discovered revenue opportunities for current merchant.
    Optionally triggers auto-detection.
    """
    if auto_detect:
        await OpportunityEngine.detect_all_opportunities(db=db, merchant_id=user.merchant_id)

    query = (
        select(Opportunity)
        .where(Opportunity.merchant_id == user.merchant_id)
        .order_by(Opportunity.estimated_value.desc(), Opportunity.detected_at.desc())
        .limit(limit)
    )

    if status_filter:
        query = query.where(Opportunity.status == status_filter.lower())
    if type_filter:
        query = query.where(Opportunity.type == type_filter.lower())

    res = await db.execute(query)
    opportunities = res.scalars().all()
    return ApiResponse.ok([OpportunityResponse.model_validate(o) for o in opportunities])


@router.get("/{opportunity_id}", response_model=ApiResponse[OpportunityDetailResponse])
async def get_opportunity_detail(
    opportunity_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve full opportunity detail, linked action plans, and simulations."""
    query = (
        select(Opportunity)
        .options(
            selectinload(Opportunity.action_plans),
            selectinload(Opportunity.simulations),
        )
        .where(
            Opportunity.id == opportunity_id,
            Opportunity.merchant_id == user.merchant_id,
        )
    )
    res = await db.execute(query)
    opp = res.scalar_one_or_none()
    if not opp:
        raise NotFoundError("Opportunity", str(opportunity_id))

    plans = [ActionPlanResponse.model_validate(p) for p in opp.action_plans]
    sims = [
        {
            "id": str(s.id),
            "simulation_type": s.simulation_type,
            "parameters": s.parameters,
            "results": s.results,
            "assumptions": s.assumptions,
            "confidence_score": float(s.confidence_score),
            "created_at": s.created_at.isoformat(),
        }
        for s in opp.simulations
    ]

    return ApiResponse.ok(
        OpportunityDetailResponse(
            opportunity=OpportunityResponse.model_validate(opp),
            action_plans=plans,
            simulations=sims,
        )
    )


@router.post("/{opportunity_id}/investigate", response_model=ApiResponse[OpportunityInvestigateResponse])
async def investigate_opportunity(
    opportunity_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Performs a deep-dive investigation into an opportunity's underlying evidence.
    Transitions status to INVESTIGATING.
    """
    try:
        diagnostics = await OpportunityEngine.investigate_opportunity(
            db=db,
            merchant_id=user.merchant_id,
            opportunity_id=opportunity_id,
        )
    except ValueError:
        raise NotFoundError("Opportunity", str(opportunity_id))

    return ApiResponse.ok(OpportunityInvestigateResponse.model_validate(diagnostics))
