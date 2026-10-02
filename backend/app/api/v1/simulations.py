"""
Flowmint AI — Simulation API Endpoints (Phase 2B).

Provides deterministic what-if scenario calculations.
Outputs are explicitly labeled as simulations/estimates with transparent formulas.
Enforces merchant ownership and tenant isolation.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user
from app.database import get_db
from app.schemas.common import ApiResponse
from app.schemas.simulation import (
    CartRecoverySimulationRequest,
    OfferDiscountSimulationRequest,
    SimulationResponse,
)
from app.services.simulation_engine import WhatIfSimulationService

router = APIRouter(prefix="/simulations", tags=["What-if Simulations"])


@router.post("/recovery", response_model=ApiResponse[SimulationResponse])
async def simulate_cart_recovery(
    data: CartRecoverySimulationRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Simulates recovery revenue, discount expenditure, and net margin impact
    for offering a discount to abandoned carts above a threshold.
    """
    sim_result = await WhatIfSimulationService.simulate_cart_recovery(
        db=db,
        merchant_id=user.merchant_id,
        discount_percent=data.discount_percent,
        min_cart_value=data.min_cart_value,
        assumed_conversion_rate=data.assumed_conversion_rate,
        opportunity_id=data.opportunity_id,
        action_plan_id=data.action_plan_id,
    )
    return ApiResponse.ok(SimulationResponse.model_validate(sim_result))


@router.post("/offer", response_model=ApiResponse[SimulationResponse])
async def simulate_promotional_offer(
    data: OfferDiscountSimulationRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Simulates revenue and order volume changes from a storewide or category promotional offer.
    """
    sim_result = await WhatIfSimulationService.simulate_offer_discount(
        db=db,
        merchant_id=user.merchant_id,
        discount_percent=data.discount_percent,
        expected_conversion_lift_pct=data.expected_conversion_lift_pct,
        opportunity_id=data.opportunity_id,
    )
    return ApiResponse.ok(SimulationResponse.model_validate(sim_result))
