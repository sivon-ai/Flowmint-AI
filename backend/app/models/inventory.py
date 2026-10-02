"""
Inventory model — tracks stock with reservation support.

Invariant: available = quantity - reserved >= 0
Uses SELECT FOR UPDATE for concurrent reservation safety.
"""

import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, generate_uuid


class Inventory(TimestampMixin, Base):
    __tablename__ = "inventory"
    __table_args__ = (
        UniqueConstraint("product_id", name="uq_inventory_product"),
        CheckConstraint("quantity >= 0", name="ck_inventory_quantity_positive"),
        CheckConstraint("reserved >= 0", name="ck_inventory_reserved_positive"),
        CheckConstraint("reserved <= quantity", name="ck_inventory_reserved_lte_quantity"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    merchant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("merchants.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reserved: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    low_stock_threshold: Mapped[int] = mapped_column(Integer, nullable=False, default=5)

    # Relationships
    product = relationship("Product", back_populates="inventory")

    @property
    def available(self) -> int:
        """Available stock = total quantity - reserved."""
        return self.quantity - self.reserved

    @property
    def is_low_stock(self) -> bool:
        return self.available <= self.low_stock_threshold

    @property
    def is_in_stock(self) -> bool:
        return self.available > 0
