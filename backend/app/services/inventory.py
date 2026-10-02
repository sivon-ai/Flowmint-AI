"""
Inventory service — stock management with reservation support.

Uses SELECT FOR UPDATE to prevent race conditions during concurrent reservation.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InsufficientStockError, NotFoundError
from app.events.bus import DomainEvent, event_bus
from app.events.types import EventType
from app.models.inventory import Inventory
from app.models.outbox import OutboxEvent
from app.models.product import Product
from app.schemas.inventory import InventoryResponse, InventoryUpdateRequest


class InventoryService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get(self, merchant_id: uuid.UUID, product_id: uuid.UUID) -> InventoryResponse:
        """Get inventory for a product."""
        result = await self.db.execute(
            select(Inventory).where(
                Inventory.product_id == product_id,
                Inventory.merchant_id == merchant_id,
            )
        )
        inv = result.scalar_one_or_none()
        if not inv:
            raise NotFoundError("Inventory", str(product_id))
        return InventoryResponse.model_validate(inv)

    async def update(
        self, merchant_id: uuid.UUID, product_id: uuid.UUID, data: InventoryUpdateRequest
    ) -> InventoryResponse:
        """Update inventory quantity or threshold."""
        result = await self.db.execute(
            select(Inventory)
            .where(
                Inventory.product_id == product_id,
                Inventory.merchant_id == merchant_id,
            )
            .with_for_update()
        )
        inv = result.scalar_one_or_none()
        if not inv:
            raise NotFoundError("Inventory", str(product_id))

        if data.quantity is not None:
            if data.quantity < inv.reserved:
                raise InsufficientStockError(
                    str(product_id), data.quantity, inv.reserved
                )
            inv.quantity = data.quantity
        if data.low_stock_threshold is not None:
            inv.low_stock_threshold = data.low_stock_threshold

        self.db.add(OutboxEvent(
            event_type=EventType.INVENTORY_UPDATED,
            aggregate_type="inventory",
            aggregate_id=str(inv.id),
            payload={
                "merchant_id": str(merchant_id),
                "product_id": str(product_id),
                "quantity": inv.quantity,
                "available": inv.available,
            },
        ))

        await self.db.commit()
        await self.db.refresh(inv)

        # Check low stock
        if inv.is_low_stock:
            await event_bus.publish(DomainEvent(
                event_type=EventType.INVENTORY_LOW,
                aggregate_type="inventory",
                aggregate_id=str(inv.id),
                payload={
                    "product_id": str(product_id),
                    "available": inv.available,
                    "threshold": inv.low_stock_threshold,
                },
                merchant_id=str(merchant_id),
            ))

        return InventoryResponse.model_validate(inv)

    async def reserve(
        self, merchant_id: uuid.UUID, product_id: uuid.UUID, quantity: int
    ) -> None:
        """
        Reserve stock for an order.
        Uses SELECT FOR UPDATE to prevent concurrent overselling.
        """
        result = await self.db.execute(
            select(Inventory)
            .where(
                Inventory.product_id == product_id,
                Inventory.merchant_id == merchant_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        inv = result.scalar_one_or_none()
        if not inv:
            raise NotFoundError("Inventory", str(product_id))

        if inv.available < quantity:
            # Get product name for error message
            prod_result = await self.db.execute(
                select(Product.name).where(Product.id == product_id)
            )
            product_name = prod_result.scalar() or str(product_id)
            raise InsufficientStockError(product_name, inv.available, quantity)

        inv.reserved += quantity
        await self.db.flush()

        self.db.add(OutboxEvent(
            event_type=EventType.INVENTORY_RESERVED,
            aggregate_type="inventory",
            aggregate_id=str(inv.id),
            payload={
                "merchant_id": str(merchant_id),
                "product_id": str(product_id),
                "reserved_qty": quantity,
            },
        ))

    async def release(
        self, merchant_id: uuid.UUID, product_id: uuid.UUID, quantity: int
    ) -> None:
        """Release reserved stock (e.g., on order cancellation)."""
        result = await self.db.execute(
            select(Inventory)
            .where(
                Inventory.product_id == product_id,
                Inventory.merchant_id == merchant_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        inv = result.scalar_one_or_none()
        if not inv:
            raise NotFoundError("Inventory", str(product_id))

        inv.reserved = max(0, inv.reserved - quantity)
        await self.db.flush()

    async def confirm_sale(
        self, merchant_id: uuid.UUID, product_id: uuid.UUID, quantity: int
    ) -> None:
        """Confirm a sale — reduce both quantity and reserved."""
        result = await self.db.execute(
            select(Inventory)
            .where(
                Inventory.product_id == product_id,
                Inventory.merchant_id == merchant_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        inv = result.scalar_one_or_none()
        if not inv:
            raise NotFoundError("Inventory", str(product_id))

        inv.quantity -= quantity
        inv.reserved = max(0, inv.reserved - quantity)
        await self.db.flush()

    async def list_for_merchant(self, merchant_id: uuid.UUID) -> list[InventoryResponse]:
        """List all inventory for a merchant."""
        result = await self.db.execute(
            select(Inventory).where(Inventory.merchant_id == merchant_id)
        )
        items = result.scalars().all()
        return [InventoryResponse.model_validate(inv) for inv in items]
