"""
Flowmint AI — Simulation Pydantic Schemas (Phase 2B).
"""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CartRecoverySimulationRequest(BaseModel):
    discount_percent: float = Field(default=10.0, ge=0.0, le=50.0, description="Discount percentage (0-50%)")
    min_cart_value: float = Field(default=1000.0, ge=0.0, description="Minimum cart total value threshold")
    assumed_conversion_rate: float = Field(default=0.15, ge=0.01, le=1.0, description="Assumed recovery conversion rate (0.01 to 1.0)")
    opportunity_id: uuid.UUID | None = Field(default=None, description="Linked Opportunity ID")
    action_plan_id: uuid.UUID | None = Field(default=None, description="Linked ActionPlan ID")


class OfferDiscountSimulationRequest(BaseModel):
    discount_percent: float = Field(default=15.0, ge=0.0, le=50.0, description="Promotional discount percentage")
    expected_conversion_lift_pct: float = Field(default=20.0, ge=0.0, le=200.0, description="Expected volume lift %")
    opportunity_id: uuid.UUID | None = Field(default=None, description="Linked Opportunity ID")


class SimulationResponse(BaseModel):
    simulation_id: str
    simulation_type: str
    parameters: dict[str, Any]
    results: dict[str, Any]
    assumptions: dict[str, Any]
    created_at: str
