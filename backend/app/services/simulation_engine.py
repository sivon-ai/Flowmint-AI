"""
Flowmint AI — What-if Simulation Engine (Phase 2B).

Provides deterministic financial models and scenario simulations.
Calculates projected recovery, discount costs, conversion projections, and margin impacts.
Persists simulation runs with explicit, inspectable assumptions.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.opportunity import SimulationRecord
from app.services.revenue_intelligence import RevenueIntelligenceService


class WhatIfSimulationService:
    """Deterministic simulation engine for merchant revenue scenarios."""

    @staticmethod
    async def simulate_cart_recovery(
        db: AsyncSession,
        merchant_id: uuid.UUID,
        discount_percent: float = 10.0,
        min_cart_value: float = 1000.0,
        assumed_conversion_rate: float = 0.15,
        opportunity_id: uuid.UUID | None = None,
        action_plan_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        """
        Simulates: "What if I offer a X% discount to abandoned carts above ₹Y?"
        """
        candidates = await RevenueIntelligenceService.get_abandoned_cart_candidates(
            db, merchant_id, min_value=Decimal(str(min_cart_value)), limit=100
        )

        eligible_count = len(candidates)
        current_value = sum(c["total_value"] for c in candidates)
        avg_cart_val = (current_value / eligible_count) if eligible_count > 0 else 0.0

        projected_conversions = round(eligible_count * assumed_conversion_rate)
        gross_recovered = round(avg_cart_val * projected_conversions, 2)
        discount_cost = round(gross_recovered * (discount_percent / 100.0), 2)
        projected_revenue = round(gross_recovered - discount_cost, 2)

        # Assuming 65% standard retail gross margin
        baseline_margin_pct = 65.0
        gross_profit_before_discount = gross_recovered * (baseline_margin_pct / 100.0)
        projected_margin_impact = round(gross_profit_before_discount - discount_cost, 2)

        confidence_score = 0.85 if eligible_count >= 5 else 0.70

        parameters = {
            "discount_percent": discount_percent,
            "min_cart_value": min_cart_value,
            "assumed_conversion_rate": assumed_conversion_rate,
        }
        results = {
            "eligible_cart_count": eligible_count,
            "current_at_risk_value": round(current_value, 2),
            "average_cart_value": round(avg_cart_val, 2),
            "assumed_conversion_rate": assumed_conversion_rate,
            "projected_conversions": projected_conversions,
            "gross_recovered_revenue": gross_recovered,
            "discount_cost": discount_cost,
            "projected_net_revenue": projected_revenue,
            "projected_margin_impact": projected_margin_impact,
            "confidence_score": confidence_score,
            "disclaimer": "SIMULATION / ESTIMATE — Calculations are deterministic projections and not guaranteed earnings.",
        }
        assumptions = {
            "baseline_gross_margin_pct": baseline_margin_pct,
            "discount_applied_on_gross": True,
            "recovery_window_days": 7,
            "customer_price_sensitivity": "standard_elastic",
        }

        # Persist simulation record
        sim = SimulationRecord(
            merchant_id=merchant_id,
            opportunity_id=opportunity_id,
            action_plan_id=action_plan_id,
            simulation_type="cart_recovery",
            parameters=parameters,
            results=results,
            assumptions=assumptions,
            confidence_score=Decimal(str(confidence_score)),
        )
        db.add(sim)
        await db.commit()
        await db.refresh(sim)

        return {
            "simulation_id": str(sim.id),
            "simulation_type": "cart_recovery",
            "parameters": parameters,
            "results": results,
            "assumptions": assumptions,
            "created_at": sim.created_at.isoformat(),
        }

    @staticmethod
    async def simulate_offer_discount(
        db: AsyncSession,
        merchant_id: uuid.UUID,
        discount_percent: float = 15.0,
        expected_conversion_lift_pct: float = 20.0,
        opportunity_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        """
        Simulates: "What if I launch a promotional offer with X% discount expecting Y% volume lift?"
        """
        overview = await RevenueIntelligenceService.get_overview_metrics(db, merchant_id)
        current_revenue = overview["total_revenue"]
        current_orders = overview["paid_orders"]
        aov = overview["average_order_value"]

        # Projected volume lift
        projected_orders = round(current_orders * (1 + expected_conversion_lift_pct / 100.0))
        lifted_order_count = projected_orders - current_orders

        gross_projected = round(projected_orders * aov, 2)
        discount_cost = round(gross_projected * (discount_percent / 100.0), 2)
        projected_net_revenue = round(gross_projected - discount_cost, 2)
        revenue_delta = round(projected_net_revenue - current_revenue, 2)

        parameters = {
            "discount_percent": discount_percent,
            "expected_conversion_lift_pct": expected_conversion_lift_pct,
        }
        results = {
            "baseline_revenue": current_revenue,
            "baseline_orders": current_orders,
            "projected_orders": projected_orders,
            "order_lift": lifted_order_count,
            "gross_projected_revenue": gross_projected,
            "discount_cost": discount_cost,
            "projected_net_revenue": projected_net_revenue,
            "net_revenue_delta": revenue_delta,
            "disclaimer": "SIMULATION / ESTIMATE — Assumes linear price elasticity based on baseline AOV.",
        }
        assumptions = {
            "elasticity_model": "linear_lift",
            "aov_constant": True,
            "evaluation_period_days": overview["period_days"],
        }

        sim = SimulationRecord(
            merchant_id=merchant_id,
            opportunity_id=opportunity_id,
            simulation_type="offer_discount",
            parameters=parameters,
            results=results,
            assumptions=assumptions,
            confidence_score=Decimal("0.75"),
        )
        db.add(sim)
        await db.commit()
        await db.refresh(sim)

        return {
            "simulation_id": str(sim.id),
            "simulation_type": "offer_discount",
            "parameters": parameters,
            "results": results,
            "assumptions": assumptions,
            "created_at": sim.created_at.isoformat(),
        }
