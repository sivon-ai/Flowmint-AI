"""
Order service — order creation from cart with inventory reservation.

Creates order → reserves inventory → emits domain event.
Order number is unique per merchant.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundError, ValidationError
from app.core.pagination import PaginationMeta, PaginationParams
from app.events.bus import DomainEvent, event_bus
from app.events.types import EventType
from app.models.cart import Cart
from app.models.order import Order, OrderItem
from app.models.outbox import OutboxEvent
from app.schemas.order import OrderCreateRequest, OrderResponse
from app.services.inventory import InventoryService


class OrderService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.inventory_service = InventoryService(db)

    async def create_from_cart(
        self, merchant_id: uuid.UUID, customer_id: uuid.UUID, data: OrderCreateRequest
    ) -> OrderResponse:
        """
        Create an order from a cart.
        1. Validate cart
        2. Generate order number
        3. Create order + order items (snapshot product data)
        4. Reserve inventory
        5. Mark cart as converted
        6. Emit event
        """
        # Get cart with items
        result = await self.db.execute(
            select(Cart)
            .options(selectinload(Cart.items))
            .where(
                Cart.id == data.cart_id,
                Cart.merchant_id == merchant_id,
            )
        )
        cart = result.scalar_one_or_none()
        if not cart:
            raise NotFoundError("Cart", str(data.cart_id))
        if cart.status != "active":
            raise ValidationError(f"Cart is in '{cart.status}' status — cannot create order")
        if not cart.items:
            raise ValidationError("Cart is empty")
        if cart.customer_id and cart.customer_id != customer_id:
            raise ValidationError("Cart does not belong to this customer")

        # Generate order number
        order_number = await self._generate_order_number(merchant_id)

        # Create order
        subtotal = cart.subtotal
        order = Order(
            merchant_id=merchant_id,
            customer_id=customer_id,
            cart_id=cart.id,
            order_number=order_number,
            status="pending",
            subtotal=subtotal,
            total=subtotal,  # No tax/discount for Phase 1
            currency="INR",
            shipping_address=data.shipping_address,
            notes=data.notes,
        )
        self.db.add(order)
        await self.db.flush()

        # Create order items and reserve inventory
        from app.models.product import Product
        for cart_item in cart.items:
            prod_result = await self.db.execute(
                select(Product).where(Product.id == cart_item.product_id)
            )
            product = prod_result.scalar_one()

            order_item = OrderItem(
                order_id=order.id,
                product_id=product.id,
                product_name=product.name,
                product_sku=product.sku,
                quantity=cart_item.quantity,
                unit_price=cart_item.unit_price,
                total=cart_item.line_total,
            )
            self.db.add(order_item)

            # Reserve inventory
            await self.inventory_service.reserve(
                merchant_id, product.id, cart_item.quantity
            )

        # Mark cart as converted
        cart.status = "converted"

        # Outbox event
        self.db.add(OutboxEvent(
            event_type=EventType.ORDER_CREATED,
            aggregate_type="order",
            aggregate_id=str(order.id),
            payload={
                "merchant_id": str(merchant_id),
                "order_number": order_number,
                "total": str(order.total),
            },
        ))

        await self.db.commit()
        await self.db.refresh(order)

        # Dispatch event
        await event_bus.publish(DomainEvent(
            event_type=EventType.ORDER_CREATED,
            aggregate_type="order",
            aggregate_id=str(order.id),
            payload={
                "order_number": order_number,
                "total": str(order.total),
                "customer_id": str(customer_id),
            },
            merchant_id=str(merchant_id),
        ))

        return OrderResponse.model_validate(order)

    async def get(self, merchant_id: uuid.UUID, order_id: uuid.UUID) -> OrderResponse:
        """Get an order by ID, scoped to merchant."""
        result = await self.db.execute(
            select(Order)
            .options(selectinload(Order.items))
            .where(Order.id == order_id, Order.merchant_id == merchant_id)
        )
        order = result.scalar_one_or_none()
        if not order:
            raise NotFoundError("Order", str(order_id))
        return OrderResponse.model_validate(order)

    async def list(
        self, merchant_id: uuid.UUID, pagination: PaginationParams
    ) -> tuple[list[OrderResponse], PaginationMeta]:
        """List orders for a merchant with pagination."""
        count_result = await self.db.execute(
            select(func.count())
            .select_from(Order)
            .where(Order.merchant_id == merchant_id)
        )
        total = count_result.scalar() or 0

        result = await self.db.execute(
            select(Order)
            .options(selectinload(Order.items))
            .where(Order.merchant_id == merchant_id)
            .order_by(Order.created_at.desc())
            .offset(pagination.offset)
            .limit(pagination.per_page)
        )
        orders = result.scalars().all()
        meta = PaginationMeta.from_params(pagination, total)
        return [OrderResponse.model_validate(o) for o in orders], meta

    async def _generate_order_number(self, merchant_id: uuid.UUID) -> str:
        """Generate a unique order number per merchant: FM-0001-A7B2C3."""
        result = await self.db.execute(
            select(func.count())
            .select_from(Order)
            .where(Order.merchant_id == merchant_id)
        )
        count = (result.scalar() or 0) + 1
        suffix = uuid.uuid4().hex[:6].upper()
        return f"FM-{count:04d}-{suffix}"
