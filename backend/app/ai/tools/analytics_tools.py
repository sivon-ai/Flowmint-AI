"""
Flowmint AI — Safe Read-Only Analytics Tools (Phase 2A).

Provides authoritative revenue, conversion, payment, and product performance data
to the Analytics Agent. Strictly read-only; all queries are scoped to context.merchant_id.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import case, func, select

from app.ai.tools.base import BaseTool, ToolContext, ToolResult
from app.models.cart import Cart
from app.models.order import Order, OrderItem
from app.models.payment import Payment


def _parse_date(d_str: str | None) -> datetime | None:
    if not d_str:
        return None
    try:
        dt = datetime.fromisoformat(d_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


# ============================================================
# 1. Get Revenue Summary Tool
# ============================================================

class RevenueSummaryParams(BaseModel):
    start_date: str | None = Field(default=None, description="ISO format start date (e.g. 2026-09-01)")
    end_date: str | None = Field(default=None, description="ISO format end date (e.g. 2026-09-30)")


class GetRevenueSummaryTool(BaseTool):
    @property
    def name(self) -> str:
        return "get_revenue_summary"

    @property
    def description(self) -> str:
        return (
            "Retrieve authoritative merchant revenue metrics from confirmed/paid orders, "
            "including total revenue, order count, and average order value (AOV)."
        )

    @property
    def parameters_schema(self) -> type[BaseModel]:
        return RevenueSummaryParams

    async def execute(self, params: RevenueSummaryParams, context: ToolContext) -> ToolResult:
        query = select(
            func.coalesce(func.sum(Order.total), Decimal("0.00")).label("total_revenue"),
            func.count(Order.id).label("order_count"),
        ).where(
            Order.merchant_id == context.merchant_id,
            Order.status.in_(["paid", "completed"]),
        )

        start_dt = _parse_date(params.start_date)
        end_dt = _parse_date(params.end_date)
        if start_dt:
            query = query.where(Order.created_at >= start_dt)
        if end_dt:
            query = query.where(Order.created_at <= end_dt)

        res = await context.db.execute(query)
        row = res.one()

        tot_rev = row.total_revenue
        cnt = row.order_count
        aov = (tot_rev / cnt) if cnt > 0 else Decimal("0.00")

        return ToolResult.ok(data={
            "total_revenue": str(tot_rev),
            "order_count": cnt,
            "average_order_value": str(round(aov, 2)),
            "currency": "INR",
            "period": {
                "start": params.start_date,
                "end": params.end_date,
            },
        })


# ============================================================
# 2. Get Conversion Summary Tool
# ============================================================

class ConversionSummaryParams(BaseModel):
    start_date: str | None = Field(default=None, description="ISO format start date")
    end_date: str | None = Field(default=None, description="ISO format end date")


class GetConversionSummaryTool(BaseTool):
    @property
    def name(self) -> str:
        return "get_conversion_summary"

    @property
    def description(self) -> str:
        return "Retrieve cart funnel metrics: total carts created, active carts, and converted carts."

    @property
    def parameters_schema(self) -> type[BaseModel]:
        return ConversionSummaryParams

    async def execute(self, params: ConversionSummaryParams, context: ToolContext) -> ToolResult:
        query = select(
            func.count(Cart.id).label("total_carts"),
            func.sum(case((Cart.status == "converted", 1), else_=0)).label("converted_carts"),
            func.sum(case((Cart.status == "active", 1), else_=0)).label("active_carts"),
            func.sum(case((Cart.status == "abandoned", 1), else_=0)).label("abandoned_carts"),
        ).where(Cart.merchant_id == context.merchant_id)

        start_dt = _parse_date(params.start_date)
        end_dt = _parse_date(params.end_date)
        if start_dt:
            query = query.where(Cart.created_at >= start_dt)
        if end_dt:
            query = query.where(Cart.created_at <= end_dt)

        res = await context.db.execute(query)
        row = res.one()

        tot = row.total_carts or 0
        conv = row.converted_carts or 0
        act = row.active_carts or 0
        aband = row.abandoned_carts or 0
        rate = round((conv / tot) * 100, 2) if tot > 0 else 0.0

        return ToolResult.ok(data={
            "total_carts": tot,
            "converted_carts": conv,
            "active_carts": act,
            "abandoned_carts": aband,
            "conversion_rate_percent": rate,
        })


# ============================================================
# 3. Get Product Performance Tool
# ============================================================

class ProductPerformanceParams(BaseModel):
    limit: int = Field(default=10, ge=1, le=50, description="Number of top products to return")
    order_by: str = Field(default="revenue", description="'revenue' or 'units_sold'")


class GetProductPerformanceTool(BaseTool):
    @property
    def name(self) -> str:
        return "get_product_performance"

    @property
    def description(self) -> str:
        return "Retrieve sales performance rankings for products based on real order history."

    @property
    def parameters_schema(self) -> type[BaseModel]:
        return ProductPerformanceParams

    async def execute(self, params: ProductPerformanceParams, context: ToolContext) -> ToolResult:
        query = (
            select(
                OrderItem.product_id,
                OrderItem.product_name,
                OrderItem.product_sku,
                func.sum(OrderItem.quantity).label("units_sold"),
                func.sum(OrderItem.total).label("total_revenue"),
            )
            .join(Order, Order.id == OrderItem.order_id)
            .where(
                Order.merchant_id == context.merchant_id,
                Order.status.in_(["paid", "completed", "pending"]),
            )
            .group_by(
                OrderItem.product_id,
                OrderItem.product_name,
                OrderItem.product_sku,
            )
        )

        if params.order_by == "units_sold":
            query = query.order_by(func.sum(OrderItem.quantity).desc())
        else:
            query = query.order_by(func.sum(OrderItem.total).desc())

        query = query.limit(params.limit)

        res = await context.db.execute(query)
        rows = res.all()

        output = [
            {
                "product_id": str(r.product_id),
                "product_name": r.product_name,
                "product_sku": r.product_sku,
                "units_sold": int(r.units_sold or 0),
                "total_revenue": float(r.total_revenue or 0.0),
            }
            for r in rows
        ]
        return ToolResult.ok(data=output, message=f"Analyzed {len(output)} product(s)")


# ============================================================
# 4. Get Payment Summary Tool
# ============================================================

class PaymentSummaryParams(BaseModel):
    start_date: str | None = Field(default=None, description="ISO format start date")
    end_date: str | None = Field(default=None, description="ISO format end date")


class GetPaymentSummaryTool(BaseTool):
    @property
    def name(self) -> str:
        return "get_payment_summary"

    @property
    def description(self) -> str:
        return "Retrieve payment processing stats: captured, failed, pending counts and amounts."

    @property
    def parameters_schema(self) -> type[BaseModel]:
        return PaymentSummaryParams

    async def execute(self, params: PaymentSummaryParams, context: ToolContext) -> ToolResult:
        query = select(
            Payment.status,
            func.count(Payment.id).label("count"),
            func.coalesce(func.sum(Payment.amount), Decimal("0.00")).label("amount"),
        ).where(Payment.merchant_id == context.merchant_id)

        start_dt = _parse_date(params.start_date)
        end_dt = _parse_date(params.end_date)
        if start_dt:
            query = query.where(Payment.created_at >= start_dt)
        if end_dt:
            query = query.where(Payment.created_at <= end_dt)

        query = query.group_by(Payment.status)
        res = await context.db.execute(query)
        rows = res.all()

        status_breakdown = {r.status: {"count": r.count, "amount": str(r.amount)} for r in rows}
        captured_amount = status_breakdown.get("captured", {}).get("amount", "0.00")
        failed_count = status_breakdown.get("failed", {}).get("count", 0)

        return ToolResult.ok(data={
            "by_status": status_breakdown,
            "total_captured_amount": captured_amount,
            "failed_attempts": failed_count,
        })


# ============================================================
# 5. Compare Periods Tool
# ============================================================

class ComparePeriodsParams(BaseModel):
    period1_start: str = Field(description="ISO start date for period 1 (e.g. 2026-09-01)")
    period1_end: str = Field(description="ISO end date for period 1 (e.g. 2026-09-15)")
    period2_start: str = Field(description="ISO start date for period 2 (e.g. 2026-09-16)")
    period2_end: str = Field(description="ISO end date for period 2 (e.g. 2026-09-30)")


class ComparePeriodsTool(BaseTool):
    @property
    def name(self) -> str:
        return "compare_periods"

    @property
    def description(self) -> str:
        return "Compare revenue and order metrics across two distinct calendar periods."

    @property
    def parameters_schema(self) -> type[BaseModel]:
        return ComparePeriodsParams

    async def execute(self, params: ComparePeriodsParams, context: ToolContext) -> ToolResult:
        async def _get_period_stats(s_str: str, e_str: str):
            s_dt = _parse_date(s_str)
            e_dt = _parse_date(e_str)
            q = select(
                func.coalesce(func.sum(Order.total), Decimal("0.00")).label("rev"),
                func.count(Order.id).label("cnt"),
            ).where(
                Order.merchant_id == context.merchant_id,
                Order.status.in_(["paid", "completed"]),
            )
            if s_dt:
                q = q.where(Order.created_at >= s_dt)
            if e_dt:
                q = q.where(Order.created_at <= e_dt)
            res = await context.db.execute(q)
            row = res.one()
            rev = row.rev
            cnt = row.cnt
            aov = (rev / cnt) if cnt > 0 else Decimal("0.00")
            return rev, cnt, aov

        p1_rev, p1_cnt, p1_aov = await _get_period_stats(params.period1_start, params.period1_end)
        p2_rev, p2_cnt, p2_aov = await _get_period_stats(params.period2_start, params.period2_end)

        rev_delta_pct = 0.0
        if p1_rev > 0:
            rev_delta_pct = float(round(((p2_rev - p1_rev) / p1_rev) * 100, 2))

        return ToolResult.ok(data={
            "period_1": {
                "start": params.period1_start,
                "end": params.period1_end,
                "revenue": str(p1_rev),
                "orders": p1_cnt,
                "aov": str(round(p1_aov, 2)),
            },
            "period_2": {
                "start": params.period2_start,
                "end": params.period2_end,
                "revenue": str(p2_rev),
                "orders": p2_cnt,
                "aov": str(round(p2_aov, 2)),
            },
            "revenue_change_percent": rev_delta_pct,
        })


# ============================================================
# 6. Get Order Summary Tool
# ============================================================

class OrderSummaryParams(BaseModel):
    status: str | None = Field(default=None, description="Optional filter by order status (pending, paid, cancelled)")
    start_date: str | None = Field(default=None, description="ISO format start date")
    end_date: str | None = Field(default=None, description="ISO format end date")
    limit: int = Field(default=10, ge=1, le=50, description="Number of recent orders to inspect")


class GetOrderSummaryTool(BaseTool):
    @property
    def name(self) -> str:
        return "get_order_summary"

    @property
    def description(self) -> str:
        return "Retrieve order counts by status and a list of recent order records."

    @property
    def parameters_schema(self) -> type[BaseModel]:
        return OrderSummaryParams

    async def execute(self, params: OrderSummaryParams, context: ToolContext) -> ToolResult:
        # Aggregation query
        agg_q = select(
            Order.status,
            func.count(Order.id).label("count"),
            func.coalesce(func.sum(Order.total), Decimal("0.00")).label("amount"),
        ).where(Order.merchant_id == context.merchant_id)

        start_dt = _parse_date(params.start_date)
        end_dt = _parse_date(params.end_date)
        if start_dt:
            agg_q = agg_q.where(Order.created_at >= start_dt)
        if end_dt:
            agg_q = agg_q.where(Order.created_at <= end_dt)

        agg_q = agg_q.group_by(Order.status)
        agg_res = await context.db.execute(agg_q)
        counts = {r.status: {"count": r.count, "total": str(r.amount)} for r in agg_res.all()}

        # Recent orders query
        rec_q = (
            select(Order)
            .where(Order.merchant_id == context.merchant_id)
            .order_by(Order.created_at.desc())
            .limit(params.limit)
        )
        if params.status:
            rec_q = rec_q.where(Order.status == params.status)
        if start_dt:
            rec_q = rec_q.where(Order.created_at >= start_dt)
        if end_dt:
            rec_q = rec_q.where(Order.created_at <= end_dt)

        rec_res = await context.db.execute(rec_q)
        recent_orders = [
            {
                "order_number": o.order_number,
                "status": o.status,
                "total": str(o.total),
                "created_at": o.created_at.isoformat(),
            }
            for o in rec_res.scalars().all()
        ]

        return ToolResult.ok(data={
            "status_breakdown": counts,
            "recent_orders": recent_orders,
        })
