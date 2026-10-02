"""
Flowmint AI — Recovery Agent (Phase 2B).

Recommendation-only revenue recovery agent.
Analyzes abandoned shopping carts, failed checkouts, and customer recovery eligibility.
Formulates structured ActionPlan proposals (status=proposed, requires_approval=True).
STRICTLY NO AUTONOMOUS MUTATIONS.
"""

from __future__ import annotations

from typing import Any

from app.ai.agents.base import AgentResult, BaseAgent
from app.ai.providers.base import LLMMessage
from app.ai.tools.base import ToolContext
from app.models.opportunity import ActionPlan, ActionPlanStatus


class RecoveryAgent(BaseAgent):
    """Recommendation-only agent for abandoned cart and failed payment recovery."""

    @property
    def name(self) -> str:
        return "recovery_agent"

    @property
    def description(self) -> str:
        return (
            "Inspects abandoned shopping carts, failed checkout payments, and conversion bottlenecks "
            "to formulate automated recovery proposals (payment retry links, personalized incentives)."
        )

    @property
    def system_prompt(self) -> str:
        return (
            "You are Flowmint AI's Recovery Agent, a bounded-autonomy revenue recovery agent. "
            "Your role is to diagnose cart abandonment and payment drop-offs, and recommend recovery strategies.\n\n"
            "CRITICAL OPERATIONAL RULES:\n"
            "1. Ground all recommendations strictly in data retrieved from tools (abandoned carts, failed payments, recovery candidates).\n"
            "2. Never hallucinate customer cart values or payment failure codes.\n"
            "3. You are RECOMMENDATION-ONLY. You MUST NOT execute any write actions (do not send messages, do not issue refunds, do not apply discounts, do not mutate state).\n"
            "4. Formulate staged ActionPlan proposals with explicit parameters, risk levels, and estimated revenue impact.\n"
            "5. Always recommend simulation before approving discount-based recovery."
        )

    @property
    def allowed_tools(self) -> list[str]:
        return [
            "get_abandoned_carts",
            "get_failed_payments",
            "get_recovery_candidates",
            "get_conversion_summary",
            "get_order_summary",
        ]

    async def execute(
        self,
        user_message: str,
        context: ToolContext,
        history: list[LLMMessage] | None = None,
    ) -> AgentResult:
        result = await super().execute(user_message, context, history)

        # Synthesize proposed ActionPlan if recovery targets exist
        action_plan_data: dict[str, Any] | None = None
        if result.tool_calls:
            for tc in result.tool_calls:
                # 1. Abandoned Carts Plan
                if tc["name"] in ("get_abandoned_carts", "get_recovery_candidates") and tc["result"]:
                    carts = (
                        tc["result"]
                        if isinstance(tc["result"], list)
                        else tc["result"].get("top_abandoned_carts", [])
                    )
                    if carts and len(carts) > 0:
                        total_at_risk = sum(c.get("total_value", 0.0) for c in carts)
                        action_plan_data = {
                            "action_type": "abandoned_cart_recovery",
                            "target": "segment:high_value_abandoners",
                            "parameters": {
                                "discount_percent": 10,
                                "min_cart_value": 2000,
                                "recovery_channel": "email_sms",
                                "validity_hours": 48,
                            },
                            "evidence": {
                                "candidate_count": len(carts),
                                "total_at_risk_value": round(total_at_risk, 2),
                                "sample_cart_ids": [c["cart_id"] for c in carts[:3]],
                            },
                            "recommendation_reason": (
                                f"Identified {len(carts)} high-intent shopping carts totalling ₹{total_at_risk:,.2f}. "
                                "Deploying an automated reminder with a 10% recovery incentive has an estimated 15% conversion lift."
                            ),
                            "estimated_impact": {
                                "projected_recovery_rate": 0.15,
                                "projected_recovered_revenue": round(total_at_risk * 0.15 * 0.9, 2),
                            },
                            "risk_level": "medium",
                            "requires_approval": True,
                            "status": ActionPlanStatus.PROPOSED.value,
                        }
                        break

                # 2. Failed Payments Plan
                if tc["name"] == "get_failed_payments" and tc["result"]:
                    payments = tc["result"]
                    if isinstance(payments, list) and len(payments) > 0:
                        total_failed = sum(p.get("amount", 0.0) for p in payments)
                        action_plan_data = {
                            "action_type": "payment_retry_nudge",
                            "target": "segment:recent_failed_payments",
                            "parameters": {
                                "retry_channel": "email",
                                "link_validity_hours": 24,
                                "retry_mode": "one_click_razorpay",
                            },
                            "evidence": {
                                "failed_count": len(payments),
                                "total_amount": round(total_failed, 2),
                                "error_codes": list({p.get("error_code") for p in payments if p.get("error_code")}),
                            },
                            "recommendation_reason": (
                                f"Found {len(payments)} dropped checkout transactions totalling ₹{total_failed:,.2f}. "
                                "A 1-click retry payment link can recover high-intent buyers without discount expense."
                            ),
                            "estimated_impact": {
                                "projected_recovery_rate": 0.25,
                                "projected_recovered_revenue": round(total_failed * 0.25, 2),
                            },
                            "risk_level": "low",
                            "requires_approval": True,
                            "status": ActionPlanStatus.PROPOSED.value,
                        }
                        break

        # Persist ActionPlan record if DB context exists
        if action_plan_data and context.db:
            plan_record = ActionPlan(
                merchant_id=context.merchant_id,
                action_type=action_plan_data["action_type"],
                target=action_plan_data["target"],
                parameters=action_plan_data["parameters"],
                evidence=action_plan_data["evidence"],
                recommendation_reason=action_plan_data["recommendation_reason"],
                estimated_impact=action_plan_data["estimated_impact"],
                risk_level=action_plan_data["risk_level"],
                requires_approval=action_plan_data["requires_approval"],
                status=ActionPlanStatus.PROPOSED.value,
            )
            context.db.add(plan_record)
            await context.db.commit()
            await context.db.refresh(plan_record)
            action_plan_data["action_id"] = str(plan_record.id)

        result.action_plan = action_plan_data
        return result
