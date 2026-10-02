"""
Merchant model — the tenant entity.

Every merchant-owned resource references merchant_id for tenant isolation.
"""

import uuid

from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, generate_uuid


class Merchant(TimestampMixin, Base):
    __tablename__ = "merchants"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    settings: Mapped[dict | None] = mapped_column(JSONB, nullable=True, default=dict)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")

    # Relationships
    users = relationship("User", back_populates="merchant", lazy="selectin")
    products = relationship("Product", back_populates="merchant", lazy="noload")
    categories = relationship("Category", back_populates="merchant", lazy="noload")
    customers = relationship("Customer", back_populates="merchant", lazy="noload")
    orders = relationship("Order", back_populates="merchant", lazy="noload")
