"""
Product and ProductAttribute models.

Multi-tenant constraints:
- UNIQUE(merchant_id, slug)
- UNIQUE(merchant_id, sku)

Products hold the catalog data; inventory is tracked separately.
"""

import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Index, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, generate_uuid


class Product(TimestampMixin, Base):
    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("merchant_id", "slug", name="uq_product_merchant_slug"),
        UniqueConstraint("merchant_id", "sku", name="uq_product_merchant_sku"),
        Index("ix_product_merchant_status", "merchant_id", "status"),
        Index("ix_product_merchant_category", "merchant_id", "category_id"),
        # pg_trgm index created via raw SQL in migration for full-text search
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    merchant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("merchants.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
    )
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    slug: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sku: Mapped[str] = mapped_column(String(100), nullable=False)
    price: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False
    )
    compare_at_price: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), nullable=True
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active"
    )  # active, draft, archived
    metadata_json: Mapped[dict | None] = mapped_column(
        "metadata", JSONB, nullable=True, default=dict
    )
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Relationships
    merchant = relationship("Merchant", back_populates="products")
    category = relationship("Category", back_populates="products")
    attributes = relationship(
        "ProductAttribute", back_populates="product",
        cascade="all, delete-orphan", lazy="selectin",
    )
    inventory = relationship(
        "Inventory", back_populates="product", uselist=False,
        cascade="all, delete-orphan", lazy="selectin",
    )


class ProductAttribute(Base):
    """Key-value attributes for products (e.g., RAM=16GB, Color=Black)."""

    __tablename__ = "product_attributes"
    __table_args__ = (
        UniqueConstraint("product_id", "key", name="uq_prodattr_product_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[str] = mapped_column(String(500), nullable=False)

    # Relationships
    product = relationship("Product", back_populates="attributes")
