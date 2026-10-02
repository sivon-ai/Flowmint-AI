"""
Flowmint AI — Revenue Intelligence Engine (Phase 2B).

Authoritative, deterministic commerce data analyzer.
Calculates real-time financial metrics, conversion funnels, revenue at risk,
cart abandonment, and payment failure metrics directly from PostgreSQL.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.cart import Cart, CartItem
from app.models.customer import Customer
from app.models.inventory import Inventory
from app.models.order import Order, OrderItem
from app.models.payment import Payment
from app.models.product import Product


class RevenueIntelligenceService:
    """Deterministic analytics engine backing merchant dashboards and agents."""

    @staticmethod
    async def get_overview_metrics(
        db: AsyncSession,
        merchant_id: uuid.UUID,
        days: int = 30,
    ) -> dict[str, Any]:
        """
        Calculates key revenue, conversion, risk, and inventory indicators.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        # 1. Orders & Revenue (paid / completed)
        order_query = select(
            func.coalesce(func.sum(Order.total), Decimal("0.00")).label("total_revenue"),
            func.count(Order.id).label("total_orders"),
        ).where(
            Order.merchant_id == merchant_id,
            Order.status == "paid",
            Order.created_at >= cutoff,
        )
        order_res = await db.execute(order_query)
        order_row = order_res.one()
        total_revenue = Decimal(str(order_row.total_revenue))
        paid_orders_count = int(order_row.total_orders)
        aov = (
            (total_revenue / paid_orders_count).quantize(Decimal("0.01"))
            if paid_orders_count > 0
            else Decimal("0.00")
        )

        # 2. Carts & Abandonment
        # Unconverted carts: active carts with items that don't have a paid order
        cart_query = (
            select(Cart)
            .options(selectinload(Cart.items))
            .where(
                Cart.merchant_id == merchant_id,
                Cart.status == "active",
                Cart.created_at >= cutoff,
            )
        )
        cart_res = await db.execute(cart_query)
        active_carts = cart_res.scalars().all()

        abandoned_cart_count = 0
        abandoned_cart_value = Decimal("0.00")
        for c in active_carts:
            if c.items and len(c.items) > 0:
                abandoned_cart_count += 1
                c_val = sum(Decimal(str(item.unit_price)) * item.quantity for item in c.items)
                abandoned_cart_value += c_val

        # Total carts created in period
        total_carts_res = await db.execute(
            select(func.count(Cart.id)).where(
                Cart.merchant_id == merchant_id, Cart.created_at >= cutoff
            )
        )
        total_carts_count = int(total_carts_res.scalar() or 0)

        # Conversion Rate & Abandonment Rate
        conversion_rate = (
            round((paid_orders_count / total_carts_count) * 100, 2)
            if total_carts_count > 0
            else 0.0
        )
        abandonment_rate = (
            round((abandoned_cart_count / total_carts_count) * 100, 2)
            if total_carts_count > 0
            else 0.0
        )

        # 3. Payments & Failure Rate
        payment_query = select(
            Payment.status,
            func.count(Payment.id).label("cnt"),
            func.coalesce(func.sum(Payment.amount), Decimal("0.00")).label("sum_amt"),
        ).where(
            Payment.merchant_id == merchant_id,
            Payment.created_at >= cutoff,
        ).group_by(Payment.status)
        pay_res = await db.execute(payment_query)
        pay_rows = pay_res.all()

        failed_payment_count = 0
        failed_payment_value = Decimal("0.00")
        total_payment_attempts = 0

        for row in pay_rows:
            cnt = int(row.cnt)
            amt = Decimal(str(row.sum_amt))
            total_payment_attempts += cnt
            if row.status == "failed":
                failed_payment_count += cnt
                failed_payment_value += amt

        payment_failure_rate = (
            round((failed_payment_count / total_payment_attempts) * 100, 2)
            if total_payment_attempts > 0
            else 0.0
        )

        # 4. Revenue at Risk = Abandoned Carts + Failed Payments
        revenue_at_risk = abandoned_cart_value + failed_payment_value

        # 5. Inventory Pressure
        inv_query = select(
            func.count(Inventory.id).label("total_tracked"),
            func.count(Inventory.id).filter(
                (Inventory.quantity - Inventory.reserved) <= Inventory.low_stock_threshold
            ).label("low_stock_count"),
            func.count(Inventory.id).filter(
                (Inventory.quantity - Inventory.reserved) <= 0
            ).label("out_of_stock_count"),
        ).where(Inventory.merchant_id == merchant_id)
        inv_res = await db.execute(inv_query)
        inv_row = inv_res.one()

        return {
            "period_days": days,
            "total_revenue": float(total_revenue),
            "paid_orders": paid_orders_count,
            "average_order_value": float(aov),
            "total_carts": total_carts_count,
            "abandoned_cart_count": abandoned_cart_count,
            "abandoned_cart_value": float(abandoned_cart_value),
            "abandonment_rate": abandonment_rate,
            "conversion_rate": conversion_rate,
            "total_payments": total_payment_attempts,
            "failed_payment_count": failed_payment_count,
            "failed_payment_value": float(failed_payment_value),
            "payment_failure_rate": payment_failure_rate,
            "revenue_at_risk": float(revenue_at_risk),
            "inventory_pressure": {
                "total_tracked": int(inv_row.total_tracked or 0),
                "low_stock_count": int(inv_row.low_stock_count or 0),
                "out_of_stock_count": int(inv_row.out_of_stock_count or 0),
            },
        }

    @staticmethod
    async def get_abandoned_cart_candidates(
        db: AsyncSession,
        merchant_id: uuid.UUID,
        min_value: Decimal = Decimal("0.00"),
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """
        Returns granular abandoned carts eligible for recovery.
        """
        query = (
            select(Cart)
            .options(
                selectinload(Cart.items).selectinload(CartItem.product),
                selectinload(Cart.customer),
            )
            .where(
                Cart.merchant_id == merchant_id,
                Cart.status == "active",
            )
            .order_by(Cart.updated_at.desc())
            .limit(limit)
        )
        res = await db.execute(query)
        carts = res.scalars().all()

        results = []
        for c in carts:
            if not c.items:
                continue
            total = sum(Decimal(str(i.unit_price)) * i.quantity for i in c.items)
            if total < min_value:
                continue
            results.append({
                "cart_id": str(c.id),
                "customer_id": str(c.customer_id) if c.customer_id else None,
                "customer_email": c.customer.email if c.customer else None,
                "customer_name": c.customer.name if c.customer else "Guest Buyer",
                "item_count": sum(i.quantity for i in c.items),
                "total_value": float(total),
                "items": [
                    {
                        "product_id": str(i.product_id),
                        "product_name": i.product.name if i.product else "Item",
                        "quantity": i.quantity,
                        "unit_price": float(i.unit_price),
                        "line_total": float(Decimal(str(i.unit_price)) * i.quantity),
                    }
                    for i in c.items
                ],
                "created_at": c.created_at.isoformat(),
                "updated_at": c.updated_at.isoformat(),
            })
        return results

    @staticmethod
    async def get_failed_payment_candidates(
        db: AsyncSession,
        merchant_id: uuid.UUID,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """
        Returns failed payment events with order and customer context.
        """
        query = (
            select(Payment)
            .options(
                selectinload(Payment.order).selectinload(Order.customer),
            )
            .where(
                Payment.merchant_id == merchant_id,
                Payment.status == "failed",
            )
            .order_by(Payment.created_at.desc())
            .limit(limit)
        )
        res = await db.execute(query)
        payments = res.scalars().all()

        results = []
        for p in payments:
            customer_email = p.order.customer.email if p.order and p.order.customer else None
            customer_name = p.order.customer.name if p.order and p.order.customer else "Customer"
            order_number = p.order.order_number if p.order else None
            results.append({
                "payment_id": str(p.id),
                "order_id": str(p.order_id),
                "order_number": order_number,
                "amount": float(p.amount),
                "currency": p.currency,
                "error_code": p.failure_reason or "PAYMENT_FAILED",
                "error_description": p.failure_reason or "Payment failed or was cancelled",
                "customer_email": customer_email,
                "customer_name": customer_name,
                "created_at": p.created_at.isoformat(),
            })
        return results

    @staticmethod
    async def get_frequently_bought_together(
        db: AsyncSession,
        merchant_id: uuid.UUID,
        product_id: uuid.UUID | None = None,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """
        Calculates co-purchased product pairs across historical multi-item orders.
        """
        # Find paid order IDs for merchant
        order_ids_res = await db.execute(
            select(Order.id).where(Order.merchant_id == merchant_id, Order.status == "paid")
        )
        order_ids = order_ids_res.scalars().all()
        if not order_ids:
            return []

        # Find items in those orders
        items_res = await db.execute(
            select(OrderItem.order_id, OrderItem.product_id, OrderItem.product_name, OrderItem.unit_price)
            .where(OrderItem.order_id.in_(order_ids))
        )
        order_items = items_res.all()

        # Group by order
        orders_map: dict[uuid.UUID, list[Any]] = {}
        for it in order_items:
            orders_map.setdefault(it.order_id, []).append(it)

        # Count pair co-occurrences
        pair_counts: dict[tuple[uuid.UUID, uuid.UUID], int] = {}
        prod_info: dict[uuid.UUID, dict[str, Any]] = {}

        for o_id, items in orders_map.items():
            if len(items) < 2:
                continue
            for i in range(len(items)):
                prod_info[items[i].product_id] = {
                    "product_id": str(items[i].product_id),
                    "product_name": items[i].product_name,
                    "price": float(items[i].unit_price),
                }
                for j in range(i + 1, len(items)):
                    p1, p2 = items[i].product_id, items[j].product_id
                    if p1 == p2:
                        continue
                    key = (p1, p2) if str(p1) < str(p2) else (p2, p1)
                    pair_counts[key] = pair_counts.get(key, 0) + 1

        sorted_pairs = sorted(pair_counts.items(), key=lambda x: x[1], reverse=True)

        results = []
        for (p1, p2), count in sorted_pairs[:limit]:
            if product_id and (p1 != product_id and p2 != product_id):
                continue
            info1 = prod_info.get(p1, {"product_id": str(p1), "product_name": "Product A", "price": 0})
            info2 = prod_info.get(p2, {"product_id": str(p2), "product_name": "Product B", "price": 0})
            results.append({
                "product_a": info1,
                "product_b": info2,
                "co_occurrence_count": count,
                "suggested_bundle_discount_pct": 10,
                "bundle_price": float(Decimal(str(info1["price"])) + Decimal(str(info2["price"]))) * 0.9,
            })
        return results
