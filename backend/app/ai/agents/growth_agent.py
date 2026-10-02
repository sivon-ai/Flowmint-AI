"""
Flowmint AI — Growth Agent (Phase 2B).

Recommendation-only revenue expansion agent.
Analyzes cross-sells, upsell bundles, and customer purchasing history.
Can formulate and persist structured ActionPlan objects (status=proposed, requires_approval=True).
STRICTLY NO AUTONOMOUS MUTATIONS.
"""

from __future__ import annotations

import json
from typing import Any

from app.ai.agents.base import AgentResult, BaseAgent
from app.ai.providers.base import LLMMessage
from app.ai.tools.base import RiskLevel, ToolContext
from app.models.opportunity import ActionPlan, ActionPlanStatus


class GrowthAgent(BaseAgent):
    """Recommendation-only agent for cross-sell, bundling, and AOV expansion."""

    @property
    def name(self) -> str:
        return "growth_agent"

    @property
    def description(self) -> str:
        return (
            "Analyzes catalog relationships, multi-item order history, and customer purchasing patterns "
            "to recommend high-converting cross-sells, product bundles, and upsell packages."
        )

    @property
    def system_prompt(self) -> str:
        return (
            "You are Flowmint AI's Growth Agent, a bounded-autonomy revenue intelligence agent. "
            "Your role is to formulate high-impact revenue expansion recommendations: cross-sells, bundles, and upsells.\n\n"
            "CRITICAL OPERATIONAL RULES:\n"
            "1. Ground all recommendations strictly in data retrieved from tools (frequently bought together, customer history, product performance).\n"
            "2. Never hallucinate product prices, companion affinities, or historical order counts.\n"
            "3. You are RECOMMENDATION-ONLY. You MUST NOT execute any write actions (do not modify prices, do not apply discounts, do not create campaigns).\n"
            "4. Distinguish between verified purchase co-occurrences and projected revenue expansion.\n"
            "5. If sufficient data is missing, recommend running a cross-sell investigation once more orders accumulate."
        )

    @property
    def allowed_tools(self) -> list[str]:
        return [
            "get_frequently_bought_together",
            "get_customer_purchase_history",
            "get_inventory_health",
            "get_product_performance",
            "get_related_products",
            "search_products",
        ]

    async def execute(
        self,
        user_message: str,
        context: ToolContext,
        history: list[LLMMessage] | None = None,
    ) -> AgentResult:
        result = await super().execute(user_message, context, history)

        # Synthesize proposed ActionPlan if cross-sell or bundle data is verified
        action_plan_data: dict[str, Any] | None = None
        if result.tool_calls:
            for tc in result.tool_calls:
                if tc["name"] == "get_frequently_bought_together" and tc["result"]:
                    pairs = tc["result"]
                    if isinstance(pairs, list) and len(pairs) > 0:
                        top = pairs[0]
                        p_a = top.get("product_a", {})
                        p_b = top.get("product_b", {})
                        action_plan_data = {
                            "action_type": "cross_sell_bundle",
                            "target": f"product_bundle:{p_a.get('product_id', 'p1')}+{p_b.get('product_id', 'p2')}",
                            "parameters": {
                                "product_a_id": p_a.get("product_id"),
                                "product_b_id": p_b.get("product_id"),
                                "suggested_discount_pct": top.get("suggested_bundle_discount_pct", 10),
                                "bundle_price": top.get("bundle_price", 0.0),
                            },
                            "evidence": {
                                "co_occurrence_count": top.get("co_occurrence_count", 0),
                                "product_a": p_a.get("product_name"),
                                "product_b": p_b.get("product_name"),
                            },
                            "recommendation_reason": (
                                f"Customers frequently purchase '{p_a.get('product_name')}' and '{p_b.get('product_name')}' together. "
                                f"Offering a {top.get('suggested_bundle_discount_pct', 10)}% bundled discount increases checkout AOV."
                            ),
                            "estimated_impact": {
                                "projected_aov_lift_pct": 12.5,
                                "projected_margin_impact": "positive",
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
