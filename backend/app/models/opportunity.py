"""
Flowmint AI — Revenue Opportunity, ActionPlan, and Simulation Models (Phase 2B).

Models:
- Opportunity: Discovered revenue opportunities with inspectable evidence.
- ActionPlan: Recommended actionable proposal (recommendation-only, no execution in Phase 2B).
- SimulationRecord: What-if simulation inputs, transparent formulas, and projected impacts.

All models enforce strict tenant isolation via merchant_id.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, generate_uuid


class OpportunityType(str, enum.Enum):
    ABANDONED_CART = "abandoned_cart"
    PAYMENT_FAILURE = "payment_failure"
    CONVERSION_DROP = "conversion_drop"
    CROSS_SELL = "cross_sell"
    UPSELL = "upsell"
    PRODUCT_DEMAND_SPIKE = "product_demand_spike"
    LOW_INVENTORY = "low_inventory"
    UNDERPERFORMING_PRODUCT = "underperforming_product"
    CUSTOMER_REACTIVATION = "customer_reactivation"


class OpportunityStatus(str, enum.Enum):
    DETECTED = "detected"
    INVESTIGATING = "investigating"
    PROPOSED = "proposed"
    SIMULATING = "simulating"
    READY_FOR_REVIEW = "ready_for_review"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"
    EXPIRED = "expired"


class ActionPlanStatus(str, enum.Enum):
    PROPOSED = "proposed"
    VALIDATING = "validating"
    SIMULATING = "simulating"
    READY_FOR_REVIEW = "ready_for_review"
    PENDING_APPROVAL = "pending_approval"
    AUTO_APPROVED = "auto_approved"
    POLICY_REJECTED = "policy_rejected"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    DEFERRED = "deferred"
    REJECTED = "rejected"
    EXPIRED = "expired"


class Opportunity(TimestampMixin, Base):
    """
    Revenue opportunity detected from live commerce patterns with verifiable evidence.
    """

    __tablename__ = "opportunities"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    merchant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("merchants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default=OpportunityStatus.DETECTED.value, index=True
    )
    priority: Mapped[str] = mapped_column(
        String(20), nullable=False, default="medium"
    )  # low, medium, high, critical
    confidence: Mapped[Decimal] = mapped_column(
        Numeric(3, 2), nullable=False, default=Decimal("0.85")
    )
    estimated_value: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    evidence_json: Mapped[dict] = mapped_column("evidence", JSONB, nullable=False, default=dict)
    affected_entity_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default="cart"
    )  # cart, payment, product, customer, category
    affected_entity_ids: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list
    )
    recommended_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    metadata_json: Mapped[dict | None] = mapped_column(
        "metadata", JSONB, nullable=True, default=dict
    )

    # Relationships
    merchant = relationship("Merchant")
    action_plans = relationship(
        "ActionPlan",
        back_populates="opportunity",
        cascade="all, delete-orphan",
        order_by="ActionPlan.created_at.desc()",
    )
    simulations = relationship(
        "SimulationRecord",
        back_populates="opportunity",
        cascade="all, delete-orphan",
        order_by="SimulationRecord.created_at.desc()",
    )


class ActionPlan(TimestampMixin, Base):
    """
    Recommended revenue action proposal produced by Growth Agent or Recovery Agent.
    Strictly recommendation-only in Phase 2B (no write execution).
    """

    __tablename__ = "action_plans"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    merchant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("merchants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    opportunity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("opportunities.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    action_type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )  # abandoned_cart_recovery, cross_sell_bundle, payment_retry_nudge, etc.
    target: Mapped[str] = mapped_column(
        String(100), nullable=False
    )  # e.g. "cart:uuid", "segment:high_value_abandoners", "product:sku"
    parameters: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    evidence: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    recommendation_reason: Mapped[str] = mapped_column(Text, nullable=False)
    estimated_impact: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    risk_level: Mapped[str] = mapped_column(
        String(20), nullable=False, default="medium"
    )  # read_only, low, medium, high, critical
    requires_approval: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default=ActionPlanStatus.PROPOSED.value, index=True
    )
    metadata_json: Mapped[dict | None] = mapped_column(
        "metadata", JSONB, nullable=True, default=dict
    )

    # Relationships
    merchant = relationship("Merchant")
    opportunity = relationship("Opportunity", back_populates="action_plans")


class SimulationRecord(Base):
    """
    Persisted results and assumptions of what-if financial simulations.
    """

    __tablename__ = "simulation_records"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    merchant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("merchants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    opportunity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("opportunities.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    action_plan_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("action_plans.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    simulation_type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )  # cart_recovery, offer_discount, price_elasticity, bundle_cross_sell
    parameters: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    results: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    assumptions: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    confidence_score: Mapped[Decimal] = mapped_column(
        Numeric(3, 2), nullable=False, default=Decimal("0.80")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    merchant = relationship("Merchant")
    opportunity = relationship("Opportunity", back_populates="simulations")
    action_plan = relationship("ActionPlan")
