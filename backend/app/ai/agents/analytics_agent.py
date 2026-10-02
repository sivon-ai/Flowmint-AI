"""
Flowmint AI — Analytics Agent (Phase 2A).

Provides merchants with revenue analysis, funnel conversion insights,
product sales performance, and payment diagnostics.
Strictly read-only; clearly separates observed facts from interpretations.
"""

from __future__ import annotations

from app.ai.agents.base import BaseAgent
from app.ai.providers.base import LLMProvider


class AnalyticsAgent(BaseAgent):
    """Specialized agent for merchant financial and performance analytics."""

    def __init__(self, provider: LLMProvider | None = None):
        super().__init__(provider)

    @property
    def name(self) -> str:
        return "analytics_agent"

    @property
    def description(self) -> str:
        return (
            "Merchant intelligence agent that analyzes revenue, orders, "
            "product performance, payments, and conversion funnels."
        )

    @property
    def allowed_tools(self) -> list[str]:
        return [
            "get_revenue_summary",
            "get_conversion_summary",
            "get_product_performance",
            "get_payment_summary",
            "compare_periods",
            "get_order_summary",
        ]

    @property
    def system_prompt(self) -> str:
        return (
            "You are Flowmint AI's Analytics Agent. Your purpose is to provide merchants with "
            "clear, factual revenue and operational analytics derived directly from their store database.\n\n"
            "MANDATORY REPORTING STRUCTURE:\n"
            "Every report must clearly distinguish:\n"
            "1. **Observed Facts**: Raw, indisputable metrics directly returned by database tools.\n"
            "2. **Derived Calculations**: Mathematically computed averages, deltas, or percentage changes.\n"
            "3. **Interpretations**: Business context explaining what the metrics indicate (e.g., potential bottlenecks).\n\n"
            "CRITICAL CONSTRAINTS:\n"
            "- NEVER invent or estimate financial numbers. If you do not have data for a specific date range, explicitly state that.\n"
            "- READ-ONLY: You cannot issue refunds, adjust prices, or modify customer records.\n"
            "- STRICT TENANT SCOPE: Only reference data returned for this merchant."
        )
