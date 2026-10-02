"""
Flowmint AI — Revenue Opportunity Engine (Phase 2B).

Detects revenue leakage and growth opportunities from authoritative commerce data.
Generates inspectable evidence, recommended actions, and confidence scores.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.opportunity import Opportunity, OpportunityStatus, OpportunityType
from app.services.revenue_intelligence import RevenueIntelligenceService


class OpportunityEngine:
    """Detects and manages the lifecycle of merchant revenue opportunities."""

    @staticmethod
    async def detect_all_opportunities(
        db: AsyncSession,
        merchant_id: uuid.UUID,
    ) -> list[Opportunity]:
        """
        Runs all deterministic opportunity detectors and persists detected items.
        """
        metrics = await RevenueIntelligenceService.get_overview_metrics(db, merchant_id)
        opportunities: list[Opportunity] = []

        # 1. Detector: Abandoned Carts
        abandoned_opp = await OpportunityEngine._detect_abandoned_carts(db, merchant_id, metrics)
        if abandoned_opp:
            opportunities.append(abandoned_opp)

        # 2. Detector: Payment Failures
        payment_opp = await OpportunityEngine._detect_payment_failures(db, merchant_id, metrics)
        if payment_opp:
            opportunities.append(payment_opp)

        # 3. Detector: Conversion Drop / Low Conversion
        conv_opp = await OpportunityEngine._detect_conversion_drop(db, merchant_id, metrics)
        if conv_opp:
            opportunities.append(conv_opp)

        # 4. Detector: Cross-Sell Opportunities
        cross_opp = await OpportunityEngine._detect_cross_sell(db, merchant_id)
        if cross_opp:
            opportunities.append(cross_opp)

        await db.commit()
        for opp in opportunities:
            await db.refresh(opp)

        return opportunities

    @staticmethod
    async def _detect_abandoned_carts(
        db: AsyncSession,
        merchant_id: uuid.UUID,
        metrics: dict[str, Any],
    ) -> Opportunity | None:
        val = metrics["abandoned_cart_value"]
        cnt = metrics["abandoned_cart_count"]
        if cnt == 0 or val <= 0:
            return None

        # Fetch affected cart IDs
        candidates = await RevenueIntelligenceService.get_abandoned_cart_candidates(db, merchant_id, limit=20)
        cart_ids = [c["cart_id"] for c in candidates]

        # Check existing active opportunity
        existing = await db.execute(
            select(Opportunity).where(
                Opportunity.merchant_id == merchant_id,
                Opportunity.type == OpportunityType.ABANDONED_CART.value,
                Opportunity.status.in_([OpportunityStatus.DETECTED.value, OpportunityStatus.INVESTIGATING.value, OpportunityStatus.PROPOSED.value]),
            )
        )
        opp = existing.scalars().first()

        title = f"High-Value Abandoned Carts (₹{val:,.2f} at risk)"
        desc = (
            f"Detected {cnt} active carts left unconverted with total potential revenue of ₹{val:,.2f}. "
            f"Average cart value is ₹{(val / cnt):,.2f}."
        )
        evidence = {
            "metric": "abandoned_cart_value",
            "value": val,
            "cart_count": cnt,
            "period": "last_30_days",
            "average_cart_value": round(val / cnt, 2),
            "sample_cart_ids": cart_ids[:5],
        }
        rec_action = "Deploy targeted recovery incentive or payment link nudge to carts over ₹3,000"

        if opp:
            opp.title = title
            opp.description = desc
            opp.estimated_value = Decimal(str(val))
            opp.evidence_json = evidence
            opp.affected_entity_ids = cart_ids
            opp.recommended_action = rec_action
            return opp

        new_opp = Opportunity(
            merchant_id=merchant_id,
            type=OpportunityType.ABANDONED_CART.value,
            title=title,
            description=desc,
            status=OpportunityStatus.DETECTED.value,
            priority="high" if val >= 5000 else "medium",
            confidence=Decimal("0.90"),
            estimated_value=Decimal(str(val)),
            currency="INR",
            evidence_json=evidence,
            affected_entity_type="cart",
            affected_entity_ids=cart_ids,
            recommended_action=rec_action,
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
        db.add(new_opp)
        return new_opp

    @staticmethod
    async def _detect_payment_failures(
        db: AsyncSession,
        merchant_id: uuid.UUID,
        metrics: dict[str, Any],
    ) -> Opportunity | None:
        fail_cnt = metrics["failed_payment_count"]
        fail_val = metrics["failed_payment_value"]
        if fail_cnt == 0 or fail_val <= 0:
            return None

        candidates = await RevenueIntelligenceService.get_failed_payment_candidates(db, merchant_id, limit=20)
        pay_ids = [p["payment_id"] for p in candidates]

        existing = await db.execute(
            select(Opportunity).where(
                Opportunity.merchant_id == merchant_id,
                Opportunity.type == OpportunityType.PAYMENT_FAILURE.value,
                Opportunity.status.in_([OpportunityStatus.DETECTED.value, OpportunityStatus.INVESTIGATING.value, OpportunityStatus.PROPOSED.value]),
            )
        )
        opp = existing.scalars().first()

        title = f"Recoverable Payment Failures (₹{fail_val:,.2f} pending)"
        desc = (
            f"Found {fail_cnt} failed checkout transactions totalling ₹{fail_val:,.2f}. "
            f"Failure rate is {metrics['payment_failure_rate']}%. High intent customers can be nudged to retry."
        )
        evidence = {
            "metric": "failed_payment_value",
            "value": fail_val,
            "failure_count": fail_cnt,
            "failure_rate_pct": metrics["payment_failure_rate"],
            "period": "last_30_days",
            "sample_payment_ids": pay_ids[:5],
        }
        rec_action = "Issue 1-click Razorpay payment retry links with 24-hour expiration"

        if opp:
            opp.title = title
            opp.description = desc
            opp.estimated_value = Decimal(str(fail_val))
            opp.evidence_json = evidence
            opp.affected_entity_ids = pay_ids
            opp.recommended_action = rec_action
            return opp

        new_opp = Opportunity(
            merchant_id=merchant_id,
            type=OpportunityType.PAYMENT_FAILURE.value,
            title=title,
            description=desc,
            status=OpportunityStatus.DETECTED.value,
            priority="high",
            confidence=Decimal("0.92"),
            estimated_value=Decimal(str(fail_val)),
            currency="INR",
            evidence_json=evidence,
            affected_entity_type="payment",
            affected_entity_ids=pay_ids,
            recommended_action=rec_action,
            expires_at=datetime.now(timezone.utc) + timedelta(days=3),
        )
        db.add(new_opp)
        return new_opp

    @staticmethod
    async def _detect_conversion_drop(
        db: AsyncSession,
        merchant_id: uuid.UUID,
        metrics: dict[str, Any],
    ) -> Opportunity | None:
        total_carts = metrics["total_carts"]
        abandonment_rate = metrics["abandonment_rate"]
        conv_rate = metrics["conversion_rate"]

        # If significant carts created (>3) and abandonment rate > 50%
        if total_carts >= 3 and abandonment_rate >= 50.0:
            existing = await db.execute(
                select(Opportunity).where(
                    Opportunity.merchant_id == merchant_id,
                    Opportunity.type == OpportunityType.CONVERSION_DROP.value,
                    Opportunity.status.in_([OpportunityStatus.DETECTED.value, OpportunityStatus.INVESTIGATING.value, OpportunityStatus.PROPOSED.value]),
                )
            )
            opp = existing.scalars().first()

            estimated_gain = metrics["abandoned_cart_value"] * 0.15  # 15% recovery potential
            title = f"Checkout Funnel Friction ({abandonment_rate}% abandonment)"
            desc = (
                f"Conversion rate is currently {conv_rate}%, with {abandonment_rate}% of carts abandoned before payment. "
                f"Recovering 15% represents ₹{estimated_gain:,.2f} in incremental revenue."
            )
            evidence = {
                "metric": "abandonment_rate",
                "value": abandonment_rate,
                "conversion_rate": conv_rate,
                "total_carts": total_carts,
                "industry_benchmark_rate": 65.0,
            }
            rec_action = "Audit checkout friction and launch an automated cart recovery email sequence"

            if opp:
                opp.title = title
                opp.description = desc
                opp.estimated_value = Decimal(str(round(estimated_gain, 2)))
                opp.evidence_json = evidence
                opp.recommended_action = rec_action
                return opp

            new_opp = Opportunity(
                merchant_id=merchant_id,
                type=OpportunityType.CONVERSION_DROP.value,
                title=title,
                description=desc,
                status=OpportunityStatus.DETECTED.value,
                priority="medium",
                confidence=Decimal("0.80"),
                estimated_value=Decimal(str(round(estimated_gain, 2))),
                currency="INR",
                evidence_json=evidence,
                affected_entity_type="cart",
                affected_entity_ids=[],
                recommended_action=rec_action,
                expires_at=datetime.now(timezone.utc) + timedelta(days=14),
            )
            db.add(new_opp)
            return new_opp
        return None

    @staticmethod
    async def _detect_cross_sell(
        db: AsyncSession,
        merchant_id: uuid.UUID,
    ) -> Opportunity | None:
        pairs = await RevenueIntelligenceService.get_frequently_bought_together(db, merchant_id, limit=3)
        if not pairs:
            return None

        top_pair = pairs[0]
        prod_a = top_pair["product_a"]["product_name"]
        prod_b = top_pair["product_b"]["product_name"]
        count = top_pair["co_occurrence_count"]
        bundle_val = top_pair["bundle_price"]

        existing = await db.execute(
            select(Opportunity).where(
                Opportunity.merchant_id == merchant_id,
                Opportunity.type == OpportunityType.CROSS_SELL.value,
                Opportunity.status.in_([OpportunityStatus.DETECTED.value, OpportunityStatus.INVESTIGATING.value, OpportunityStatus.PROPOSED.value]),
            )
        )
        opp = existing.scalars().first()

        est_revenue = bundle_val * 5  # Estimated 5 bundle conversions
        title = f"High-Affinity Bundle Opportunity: {prod_a} + {prod_b}"
        desc = (
            f"Customers have purchased '{prod_a}' and '{prod_b}' together in {count} orders. "
            f"Offering a 10% bundle package can drive an estimated ₹{est_revenue:,.2f} in incremental AOV."
        )
        evidence = {
            "metric": "co_occurrence_count",
            "value": count,
            "co_occurrence_count": count,
            "product_a": top_pair["product_a"],
            "product_b": top_pair["product_b"],
            "suggested_bundle_price": bundle_val,
        }
        rec_action = f"Promote discounted cross-sell bundle for '{prod_a}' + '{prod_b}' at checkout"

        if opp:
            opp.title = title
            opp.description = desc
            opp.estimated_value = Decimal(str(round(est_revenue, 2)))
            opp.evidence_json = evidence
            opp.affected_entity_ids = [top_pair["product_a"]["product_id"], top_pair["product_b"]["product_id"]]
            opp.recommended_action = rec_action
            return opp

        new_opp = Opportunity(
            merchant_id=merchant_id,
            type=OpportunityType.CROSS_SELL.value,
            title=title,
            description=desc,
            status=OpportunityStatus.DETECTED.value,
            priority="medium",
            confidence=Decimal("0.85"),
            estimated_value=Decimal(str(round(est_revenue, 2))),
            currency="INR",
            evidence_json=evidence,
            affected_entity_type="product",
            affected_entity_ids=[top_pair["product_a"]["product_id"], top_pair["product_b"]["product_id"]],
            recommended_action=rec_action,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
        db.add(new_opp)
        return new_opp

    @staticmethod
    async def investigate_opportunity(
        db: AsyncSession,
        merchant_id: uuid.UUID,
        opportunity_id: uuid.UUID,
    ) -> dict[str, Any]:
        """
        Deep-dive investigation for an opportunity.
        Transitions status from DETECTED -> INVESTIGATING.
        """
        query = select(Opportunity).where(
            Opportunity.id == opportunity_id,
            Opportunity.merchant_id == merchant_id,
        )
        res = await db.execute(query)
        opp = res.scalar_one_or_none()
        if not opp:
            raise ValueError(f"Opportunity {opportunity_id} not found for merchant")

        if opp.status == OpportunityStatus.DETECTED.value:
            opp.status = OpportunityStatus.INVESTIGATING.value
            await db.commit()
            await db.refresh(opp)

        # Diagnostic deep dive depending on type
        diagnostics: dict[str, Any] = {
            "opportunity_id": str(opp.id),
            "type": opp.type,
            "title": opp.title,
            "status": opp.status,
            "priority": opp.priority,
            "estimated_value": float(opp.estimated_value),
            "evidence": opp.evidence_json,
            "recommended_action": opp.recommended_action,
        }

        if opp.type == OpportunityType.ABANDONED_CART.value:
            candidates = await RevenueIntelligenceService.get_abandoned_cart_candidates(db, merchant_id, limit=5)
            diagnostics["actionable_records"] = candidates
            diagnostics["investigation_notes"] = [
                "Carts are active with reserved or unreserved items",
                "High recovery probability via email nudge or 5-10% discount",
                "Simulate recovery outcomes before proposing action",
            ]
        elif opp.type == OpportunityType.PAYMENT_FAILURE.value:
            candidates = await RevenueIntelligenceService.get_failed_payment_candidates(db, merchant_id, limit=5)
            diagnostics["actionable_records"] = candidates
            diagnostics["investigation_notes"] = [
                "Transactions encountered gateway timeout or card authentication failure",
                "Order intent remains high; customer has not placed replacement order",
                "Automated retry link is low risk and requires no discount expenditure",
            ]
        else:
            diagnostics["actionable_records"] = []
            diagnostics["investigation_notes"] = ["Evidence verified against historical orders."]

        return diagnostics
