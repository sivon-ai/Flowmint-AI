"""
Flowmint AI — Controlled Write Tools (Phase 3).

Strictly bounded write tools executed exclusively through ActionExecutionService
after passing permission, policy, risk, and approval checks.
Agents are never permitted to invoke these tools directly.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field

from app.ai.permissions import AgentCapability
from app.ai.tools.base import BaseTool, RiskLevel, ToolContext, ToolResult
from app.models.governance import Campaign, Offer


class CreateCampaignDraftParams(BaseModel):
    name: str = Field(..., description="Campaign name")
    campaign_type: str = Field(..., description="Type of campaign: cross_sell_bundle, promotional_offer")
    discount_percentage: float = Field(..., ge=0.0, le=50.0, description="Discount percentage")
    budget: float = Field(..., ge=0.0, description="Campaign monetary budget cap")
    target_criteria: dict[str, Any] = Field(default_factory=dict, description="Target segments, product IDs or cart filters")
    action_plan_id: str | None = Field(None, description="Linked ActionPlan UUID")


class CreateCampaignDraftTool(BaseTool):
    name = "create_campaign_draft"
    description = "Creates a bounded campaign draft record in the merchant database."
    parameters_schema = CreateCampaignDraftParams
    risk_level = RiskLevel.MEDIUM
    is_read_only = False
    required_capability = AgentCapability.EXECUTE_CAMPAIGN_DRAFT

    async def execute(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        if not context.db:
            return ToolResult.fail("Database session missing from tool context")

        action_plan_uuid = None
        if params.get("action_plan_id"):
            try:
                action_plan_uuid = uuid.UUID(str(params["action_plan_id"]))
            except ValueError:
                pass

        campaign = Campaign(
            merchant_id=context.merchant_id,
            action_plan_id=action_plan_uuid,
            name=params["name"],
            type=params["campaign_type"],
            status="draft",
            discount_percentage=Decimal(str(params["discount_percentage"])),
            budget=Decimal(str(params["budget"])),
            target_criteria=params.get("target_criteria", {}),
            metadata_json={"created_via": "ActionExecutionService", "trace_id": context.trace_id},
        )
        context.db.add(campaign)
        await context.db.flush()

        return ToolResult.ok(
            data={
                "campaign_id": str(campaign.id),
                "name": campaign.name,
                "type": campaign.type,
                "status": campaign.status,
                "discount_percentage": float(campaign.discount_percentage),
                "budget": float(campaign.budget),
            },
            message=f"Campaign draft '{campaign.name}' created with ID {campaign.id}",
        )


class CreateOfferParams(BaseModel):
    code: str = Field(..., description="Unique promotional discount coupon code")
    discount_percentage: float = Field(..., ge=1.0, le=50.0, description="Discount percentage")
    min_order_value: float = Field(0.0, ge=0.0, description="Minimum order threshold in store currency")
    validity_days: int = Field(7, ge=1, le=90, description="Offer validity period in days")
    action_plan_id: str | None = Field(None, description="Linked ActionPlan UUID")


class CreateOfferTool(BaseTool):
    name = "create_offer"
    description = "Generates a bounded promotional discount offer code."
    parameters_schema = CreateOfferParams
    risk_level = RiskLevel.MEDIUM
    is_read_only = False
    required_capability = AgentCapability.EXECUTE_OFFER

    async def execute(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        if not context.db:
            return ToolResult.fail("Database session missing from tool context")

        action_plan_uuid = None
        if params.get("action_plan_id"):
            try:
                action_plan_uuid = uuid.UUID(str(params["action_plan_id"]))
            except ValueError:
                pass

        expires_at = datetime.now(timezone.utc) + timedelta(days=params.get("validity_days", 7))

        offer = Offer(
            merchant_id=context.merchant_id,
            action_plan_id=action_plan_uuid,
            code=params["code"].strip().upper(),
            discount_percentage=Decimal(str(params["discount_percentage"])),
            min_order_value=Decimal(str(params.get("min_order_value", 0))),
            status="active",
            expires_at=expires_at,
            metadata_json={"created_via": "ActionExecutionService", "trace_id": context.trace_id},
        )
        context.db.add(offer)
        await context.db.flush()

        return ToolResult.ok(
            data={
                "offer_id": str(offer.id),
                "code": offer.code,
                "discount_percentage": float(offer.discount_percentage),
                "min_order_value": float(offer.min_order_value),
                "expires_at": offer.expires_at.isoformat(),
                "status": offer.status,
            },
            message=f"Offer '{offer.code}' created with ID {offer.id}",
        )


class LaunchRecoveryCampaignParams(BaseModel):
    name: str = Field(..., description="Recovery campaign name")
    cart_ids: list[str] = Field(default_factory=list, description="Target abandoned cart IDs")
    discount_percentage: float = Field(10.0, ge=0.0, le=25.0, description="Recovery discount incentive")
    action_plan_id: str | None = Field(None, description="Linked ActionPlan UUID")


class LaunchRecoveryCampaignTool(BaseTool):
    name = "launch_recovery_campaign"
    description = "Activates a recovery campaign queue for eligible abandoned carts."
    parameters_schema = LaunchRecoveryCampaignParams
    risk_level = RiskLevel.HIGH
    is_read_only = False
    required_capability = AgentCapability.EXECUTE_RECOVERY_CAMPAIGN

    async def execute(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        if not context.db:
            return ToolResult.fail("Database session missing from tool context")

        action_plan_uuid = None
        if params.get("action_plan_id"):
            try:
                action_plan_uuid = uuid.UUID(str(params["action_plan_id"]))
            except ValueError:
                pass

        campaign = Campaign(
            merchant_id=context.merchant_id,
            action_plan_id=action_plan_uuid,
            name=params["name"],
            type="abandoned_cart_recovery",
            status="active",
            discount_percentage=Decimal(str(params.get("discount_percentage", 10.0))),
            budget=Decimal("0.00"),
            target_criteria={"cart_ids": params.get("cart_ids", [])},
            metadata_json={
                "enrolled_cart_count": len(params.get("cart_ids", [])),
                "created_via": "ActionExecutionService",
                "trace_id": context.trace_id,
            },
        )
        context.db.add(campaign)
        await context.db.flush()

        return ToolResult.ok(
            data={
                "campaign_id": str(campaign.id),
                "name": campaign.name,
                "type": campaign.type,
                "status": campaign.status,
                "discount_percentage": float(campaign.discount_percentage),
                "target_cart_count": len(params.get("cart_ids", [])),
            },
            message=f"Recovery campaign '{campaign.name}' activated for {len(params.get('cart_ids', []))} carts.",
        )


class ControlledWriteToolRegistry:
    """
    Dedicated registry for controlled write tools.
    Inaccessible directly to conversational LLMs.
    """

    def __init__(self):
        self._tools: dict[str, BaseTool] = {
            "create_campaign_draft": CreateCampaignDraftTool(),
            "create_offer": CreateOfferTool(),
            "launch_recovery_campaign": LaunchRecoveryCampaignTool(),
        }

    def get(self, name: str) -> BaseTool | None:
        return self._tools.get(name)

    @property
    def tools(self) -> dict[str, BaseTool]:
        return self._tools


controlled_write_registry = ControlledWriteToolRegistry()
