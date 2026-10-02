"""
Flowmint AI — Deterministic Risk Classification Engine (Phase 3).

Evaluates action parameters, financial exposure, audience scope, and side effects.
The LLM is strictly prohibited from setting or overriding the final risk level.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.models.governance import MerchantPolicy, RiskLevel
from app.models.opportunity import ActionPlan


class RiskEngine:
    """
    Deterministic risk classifier for revenue action plans and tool executions.
    """

    @staticmethod
    def classify(action_plan: ActionPlan, policy: MerchantPolicy | None = None) -> tuple[RiskLevel, list[str]]:
        """
        Determines the risk level based on monetary value, discount percentage,
        affected audience, and reversibility.
        Returns (RiskLevel, list_of_risk_factors).
        """
        factors: list[str] = []
        p = action_plan.parameters or {}

        # 1. Prohibited / Critical actions
        if action_plan.action_type in ("refund", "chargeback_reversal", "direct_payout", "price_override"):
            factors.append("Direct financial settlement or price override involves irreversible monetary mutation.")
            return RiskLevel.CRITICAL, factors

        # 2. Financial exposure & discount magnitude
        discount_pct = Decimal(str(p.get("discount_percentage", 0)))
        budget = Decimal(str(p.get("budget", 0)))
        est_val = Decimal(str(action_plan.estimated_impact.get("projected_revenue", 0) if action_plan.estimated_impact else 0))

        # Check against merchant policy threshold if available
        high_val_threshold = (
            policy.high_value_threshold
            if policy and policy.high_value_threshold is not None
            else Decimal("10000.00")
        )
        max_discount_limit = (
            policy.max_discount_percentage
            if policy and policy.max_discount_percentage is not None
            else Decimal("15.00")
        )

        # Audience scope
        affected_count = len(p.get("cart_ids", [])) or len(p.get("customer_ids", [])) or int(p.get("eligible_count", 0))

        # 3. High Risk Conditions
        if discount_pct > max_discount_limit:
            factors.append(f"Discount percentage ({discount_pct}%) exceeds standard limit ({max_discount_limit}%).")
        if budget >= Decimal("25000.00") or est_val >= high_val_threshold * 2:
            factors.append(f"Financial exposure (Budget: ₹{budget}, Value: ₹{est_val}) exceeds high-value threshold.")
        if affected_count >= 100:
            factors.append(f"Large blast radius: affects {affected_count} customer sessions simultaneously.")
        if action_plan.action_type in ("launch_recovery_campaign", "mass_promotional_broadcast"):
            factors.append("Active live campaign launch involves external communication side effects.")

        if len(factors) >= 2 or discount_pct > Decimal("20.00") or budget >= Decimal("50000.00"):
            return RiskLevel.HIGH, factors

        # 4. Medium Risk Conditions
        if discount_pct > Decimal("5.00") or budget > Decimal("2000.00") or est_val >= high_val_threshold:
            factors.append("Moderate monetary discount or budget allocation.")
        if affected_count >= 20:
            factors.append(f"Multi-customer impact ({affected_count} entities).")
        if action_plan.action_type == "launch_recovery_campaign":
            factors.append("Live recovery campaign activation.")

        if factors:
            return RiskLevel.MEDIUM, factors

        # 5. Low Risk (Drafts, small targeted offers, internal analysis)
        factors.append("Bounded draft action with low financial exposure and limited audience.")
        return RiskLevel.LOW, factors
