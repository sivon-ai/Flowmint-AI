"""
Flowmint AI — Growth and Recovery Tools (Phase 2B).

STRICTLY READ-ONLY commerce analysis tools for:
- Growth Agent: bundle/cross-sell analysis, customer purchase patterns, inventory health
- Recovery Agent: abandoned cart retrieval, failed payment inspection, recovery candidate identification

NO MUTATING WRITE ACTIONS. ZERO autonomous discounts, campaigns, refunds, or mutations.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.ai.security.sanitizer import wrap_untrusted_data
from app.ai.tools.base import BaseTool, RiskLevel, ToolContext, ToolResult
from app.models.cart import Cart
from app.models.customer import Customer
from app.models.inventory import Inventory
from app.models.order import Order, OrderItem
from app.models.payment import Payment
from app.models.product import Product
from app.services.revenue_intelligence import RevenueIntelligenceService


# -----------------------------------------------------------------------------
# Growth Agent Tools (Read-Only)
# -----------------------------------------------------------------------------

class FrequentlyBoughtTogetherParams(BaseModel):
    product_id: str | None = Field(default=None, description="Optional product UUID to find companion items for")
    limit: int = Field(default=5, ge=1, le=20, description="Maximum bundles to return")


class FrequentlyBoughtTogetherTool(BaseTool):
    @property
    def name(self) -> str:
        return "get_frequently_bought_together"

    @property
    def description(self) -> str:
        return (
            "Analyzes order history to find product pairs frequently purchased together. "
            "Returns co-occurrence frequency, product details, and suggested bundle pricing."
        )

    @property
    def parameters_schema(self) -> type[BaseModel]:
        return FrequentlyBoughtTogetherParams

    async def execute(self, params: FrequentlyBoughtTogetherParams, context: ToolContext) -> ToolResult:
        if not context.db:
            return ToolResult(tool_name=self.name, success=False, error_message="Database session required")

        prod_uuid = uuid.UUID(params.product_id) if params.product_id else None
        pairs = await RevenueIntelligenceService.get_frequently_bought_together(
            context.db, context.merchant_id, product_id=prod_uuid, limit=params.limit
        )

        return ToolResult(
            tool_name=self.name,
            success=True,
            data=pairs,
            raw_output=wrap_untrusted_data(pairs),
        )


class CustomerPurchaseHistoryParams(BaseModel):
    customer_id: str | None = Field(default=None, description="Customer UUID")
    email: str | None = Field(default=None, description="Customer email address")


class CustomerPurchaseHistoryTool(BaseTool):
    @property
    def name(self) -> str:
        return "get_customer_purchase_history"

    @property
    def description(self) -> str:
        return "Retrieves customer order history, total lifetime spend, and frequent product categories."

    @property
    def parameters_schema(self) -> type[BaseModel]:
        return CustomerPurchaseHistoryParams

    async def execute(self, params: CustomerPurchaseHistoryParams, context: ToolContext) -> ToolResult:
        if not context.db:
            return ToolResult(tool_name=self.name, success=False, error_message="Database session required")

        query = select(Customer).where(Customer.merchant_id == context.merchant_id)
        if params.customer_id:
            try:
                query = query.where(Customer.id == uuid.UUID(params.customer_id))
            except ValueError:
                return ToolResult(tool_name=self.name, success=False, error_message="Invalid customer UUID")
        elif params.email:
            query = query.where(Customer.email == params.email.strip().lower())
        else:
            return ToolResult(tool_name=self.name, success=False, error_message="customer_id or email required")

        res = await context.db.execute(query)
        customer = res.scalar_one_or_none()
        if not customer:
            return ToolResult(
                tool_name=self.name,
                success=True,
                data=None,
                raw_output="Customer not found in merchant records.",
            )

        # Get orders
        orders_res = await context.db.execute(
            select(Order)
            .options(selectinload(Order.items))
            .where(Order.merchant_id == context.merchant_id, Order.customer_id == customer.id)
            .order_by(Order.created_at.desc())
        )
        orders = orders_res.scalars().all()

        total_spend = sum(o.total for o in orders if o.status == "paid")
        data = {
            "customer_id": str(customer.id),
            "name": customer.name,
            "email": customer.email,
            "order_count": len(orders),
            "lifetime_spend": float(total_spend),
            "recent_orders": [
                {
                    "order_id": str(o.id),
                    "order_number": o.order_number,
                    "status": o.status,
                    "total": float(o.total),
                    "items": [i.product_name for i in o.items],
                    "date": o.created_at.isoformat(),
                }
                for o in orders[:5]
            ],
        }

        return ToolResult(tool_name=self.name, success=True, data=data, raw_output=wrap_untrusted_data(data))


class InventoryHealthParams(BaseModel):
    limit: int = Field(default=20, ge=1, le=50, description="Max inventory items")


class InventoryHealthTool(BaseTool):
    @property
    def name(self) -> str:
        return "get_inventory_health"

    @property
    def description(self) -> str:
        return "Inspects product inventory health, low stock thresholds, and stockout pressure."

    @property
    def parameters_schema(self) -> type[BaseModel]:
        return InventoryHealthParams

    async def execute(self, params: InventoryHealthParams, context: ToolContext) -> ToolResult:
        if not context.db:
            return ToolResult(tool_name=self.name, success=False, error_message="Database session required")

        query = (
            select(Inventory, Product)
            .join(Product, Inventory.product_id == Product.id)
            .where(Inventory.merchant_id == context.merchant_id)
            .order_by((Inventory.quantity - Inventory.reserved).asc())
            .limit(params.limit)
        )
        res = await context.db.execute(query)
        rows = res.all()

        items = []
        for inv, prod in rows:
            available = inv.quantity - inv.reserved
            items.append({
                "product_id": str(prod.id),
                "sku": prod.sku,
                "name": prod.name,
                "quantity": inv.quantity,
                "reserved": inv.reserved,
                "available": available,
                "low_stock_threshold": inv.low_stock_threshold,
                "status": "out_of_stock" if available <= 0 else "low_stock" if available <= inv.low_stock_threshold else "healthy",
            })

        return ToolResult(tool_name=self.name, success=True, data=items, raw_output=wrap_untrusted_data(items))


# -----------------------------------------------------------------------------
# Recovery Agent Tools (Read-Only)
# -----------------------------------------------------------------------------

class AbandonedCartsParams(BaseModel):
    min_value: float = Field(default=0.0, ge=0.0, description="Minimum cart value filter in INR")
    limit: int = Field(default=20, ge=1, le=50, description="Max carts to return")


class AbandonedCartsTool(BaseTool):
    @property
    def name(self) -> str:
        return "get_abandoned_carts"

    @property
    def description(self) -> str:
        return "Fetches active, unconverted shopping carts with item breakdown and customer details."

    @property
    def parameters_schema(self) -> type[BaseModel]:
        return AbandonedCartsParams

    async def execute(self, params: AbandonedCartsParams, context: ToolContext) -> ToolResult:
        if not context.db:
            return ToolResult(tool_name=self.name, success=False, error_message="Database session required")

        candidates = await RevenueIntelligenceService.get_abandoned_cart_candidates(
            context.db, context.merchant_id, min_value=Decimal(str(params.min_value)), limit=params.limit
        )

        return ToolResult(tool_name=self.name, success=True, data=candidates, raw_output=wrap_untrusted_data(candidates))


class FailedPaymentsParams(BaseModel):
    limit: int = Field(default=20, ge=1, le=50, description="Max failed payment events")


class FailedPaymentsTool(BaseTool):
    @property
    def name(self) -> str:
        return "get_failed_payments"

    @property
    def description(self) -> str:
        return "Fetches failed checkout payments, gateway error codes, and customer recovery targets."

    @property
    def parameters_schema(self) -> type[BaseModel]:
        return FailedPaymentsParams

    async def execute(self, params: FailedPaymentsParams, context: ToolContext) -> ToolResult:
        if not context.db:
            return ToolResult(tool_name=self.name, success=False, error_message="Database session required")

        payments = await RevenueIntelligenceService.get_failed_payment_candidates(
            context.db, context.merchant_id, limit=params.limit
        )

        return ToolResult(tool_name=self.name, success=True, data=payments, raw_output=wrap_untrusted_data(payments))


class RecoveryCandidatesParams(BaseModel):
    limit: int = Field(default=10, ge=1, le=30, description="Max candidates per category")


class RecoveryCandidatesTool(BaseTool):
    @property
    def name(self) -> str:
        return "get_recovery_candidates"

    @property
    def description(self) -> str:
        return "Aggregates all high-priority recovery targets: abandoned carts and failed payment attempts."

    @property
    def parameters_schema(self) -> type[BaseModel]:
        return RecoveryCandidatesParams

    async def execute(self, params: RecoveryCandidatesParams, context: ToolContext) -> ToolResult:
        if not context.db:
            return ToolResult(tool_name=self.name, success=False, error_message="Database session required")

        carts = await RevenueIntelligenceService.get_abandoned_cart_candidates(
            context.db, context.merchant_id, limit=params.limit
        )
        payments = await RevenueIntelligenceService.get_failed_payment_candidates(
            context.db, context.merchant_id, limit=params.limit
        )

        data = {
            "abandoned_carts_count": len(carts),
            "abandoned_carts_value": sum(c["total_value"] for c in carts),
            "failed_payments_count": len(payments),
            "failed_payments_value": sum(p["amount"] for p in payments),
            "top_abandoned_carts": carts[:5],
            "top_failed_payments": payments[:5],
        }

        return ToolResult(tool_name=self.name, success=True, data=data, raw_output=wrap_untrusted_data(data))
