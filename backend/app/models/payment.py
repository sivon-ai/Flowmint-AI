"""
Payment and PaymentEvent models.

Payment state machine:
  PENDING → AUTHORIZED → CAPTURED (success path)
  PENDING → FAILED
  CAPTURED → REFUNDED

Only valid transitions are allowed — enforced by PaymentService.
Idempotency enforced via unique idempotency_key.
PaymentEvent deduplication via unique provider_event_id.
"""

import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Index, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, generate_uuid


# Valid payment state transitions (from → set of valid to-states)
PAYMENT_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"authorized", "captured", "failed"},
    "authorized": {"captured", "failed"},
    "captured": {"refunded"},
    "failed": set(),       # terminal
    "refunded": set(),     # terminal
}


class Payment(TimestampMixin, Base):
    __tablename__ = "payments"
    __table_args__ = (
        UniqueConstraint("merchant_id", "idempotency_key", name="uq_payment_merchant_idempotency"),
        Index("ix_payment_merchant_status", "merchant_id", "status"),
        Index("ix_payment_provider_order", "provider_order_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    merchant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("merchants.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )  # pending, authorized, captured, failed, refunded
    provider: Mapped[str] = mapped_column(String(50), nullable=False, default="razorpay")
    provider_order_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    provider_payment_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(
        "metadata", JSONB, nullable=True, default=dict
    )

    # Relationships
    order = relationship("Order", back_populates="payments")
    events = relationship(
        "PaymentEvent", back_populates="payment",
        cascade="all, delete-orphan", lazy="selectin",
    )

    def can_transition_to(self, new_status: str) -> bool:
        """Check if a state transition is valid."""
        return new_status in PAYMENT_TRANSITIONS.get(self.status, set())


class PaymentEvent(TimestampMixin, Base):
    """
    Immutable record of payment provider events (e.g., Razorpay webhooks).
    provider_event_id is unique to prevent duplicate webhook processing.
    """

    __tablename__ = "payment_events"
    __table_args__ = (
        UniqueConstraint("provider_event_id", name="uq_payment_event_provider_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    payment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("payments.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    provider_event_id: Mapped[str] = mapped_column(String(255), nullable=False)
    raw_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Relationships
    payment = relationship("Payment", back_populates="events")
