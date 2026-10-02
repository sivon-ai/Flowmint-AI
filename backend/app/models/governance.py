"""
Flowmint AI — Governance, Policy, Approval, Execution & Audit Models (Phase 3).

Models:
- MerchantPolicy: Configurable risk, discount, and budget policy constraints per tenant.
- Approval: Human-in-the-loop review and decision workflow for ActionPlans.
- ActionExecution: Idempotent execution record tracking write tool dispatch and outcomes.
- AuditLog: Immutable append-only audit trail capturing all safety and execution events.
- Campaign: Bounded campaign entities managed through controlled execution.
- Offer: Bounded discount offers created through controlled execution.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, generate_uuid


class ApprovalStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class ExecutionStatus(str, enum.Enum):
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"


class RiskLevel(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class MerchantPolicy(TimestampMixin, Base):
    """
    Configurable merchant business policies and autonomy bounds.
    """

    __tablename__ = "merchant_policies"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    merchant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("merchants.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    max_discount_percentage: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=Decimal("15.00")
    )
    max_campaign_budget: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("50000.00")
    )
    high_value_threshold: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("10000.00")
    )
    contact_cooldown_hours: Mapped[int] = mapped_column(
        nullable=False, default=24
    )
    require_approval_all_actions: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    auto_approval_max_risk: Mapped[str] = mapped_column(
        String(20), nullable=False, default="low"
    )
    allowed_action_types: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=lambda: [
            "abandoned_cart_recovery",
            "cross_sell_bundle",
            "promotional_offer",
            "payment_retry_nudge",
        ],
    )
    restricted_product_ids: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    metadata_json: Mapped[dict | None] = mapped_column(
        "metadata", JSONB, nullable=True, default=dict
    )

    merchant = relationship("Merchant")


class Approval(TimestampMixin, Base):
    """
    Human-in-the-loop approval record for an ActionPlan.
    """

    __tablename__ = "approvals"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    merchant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("merchants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    action_plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("action_plans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    requested_by: Mapped[str] = mapped_column(
        String(50), nullable=False, default="growth_agent"
    )
    risk_level: Mapped[str] = mapped_column(
        String(20), nullable=False, default="medium"
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default=ApprovalStatus.PENDING.value, index=True
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    decided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    decided_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    decision_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    policy_snapshot: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict
    )

    merchant = relationship("Merchant")
    action_plan = relationship("ActionPlan")
    decider = relationship("User")


class ActionExecution(Base):
    """
    Idempotent execution record tracking controlled tool invocations and side effects.
    """

    __tablename__ = "action_executions"
    __table_args__ = (
        UniqueConstraint(
            "merchant_id", "idempotency_key", name="uq_merchant_idempotency_key"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    merchant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("merchants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    action_plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("action_plans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    idempotency_key: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default=ExecutionStatus.EXECUTING.value, index=True
    )
    tool_name: Mapped[str] = mapped_column(String(100), nullable=False)
    tool_parameters: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    tool_result: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    merchant = relationship("Merchant")
    action_plan = relationship("ActionPlan")


class AuditLog(Base):
    """
    Immutable, append-only audit trail capturing all safety, policy, approval, and execution events.
    Must never be deleted or modified through application APIs.
    """

    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    merchant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("merchants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_id: Mapped[str] = mapped_column(
        String(100), nullable=False, unique=True, index=True
    )
    actor_type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )  # agent, user, system
    actor_id: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True
    )
    action_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("action_plans.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    agent: Mapped[str | None] = mapped_column(String(50), nullable=True)
    event_type: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True
    )  # action.proposed, policy.evaluated, approval.requested, approval.decided, action.executed, action.blocked
    previous_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    new_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    policy_results: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, default=dict
    )
    approval_result: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, default=dict
    )
    execution_result: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, default=dict
    )
    trace_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    merchant = relationship("Merchant")
    action_plan = relationship("ActionPlan")


class Campaign(TimestampMixin, Base):
    """
    Bounded campaign entity created via controlled action execution.
    """

    __tablename__ = "campaigns"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    merchant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("merchants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    action_plan_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("action_plans.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )  # cross_sell_bundle, abandoned_cart_recovery, promotional_offer
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="draft", index=True
    )  # draft, active, completed, paused
    discount_percentage: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=Decimal("0.00")
    )
    target_criteria: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    budget: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    metadata_json: Mapped[dict | None] = mapped_column(
        "metadata", JSONB, nullable=True, default=dict
    )

    merchant = relationship("Merchant")
    action_plan = relationship("ActionPlan")


class Offer(TimestampMixin, Base):
    """
    Bounded discount offer entity created via controlled action execution.
    """

    __tablename__ = "offers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    merchant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("merchants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    action_plan_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("action_plans.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    discount_percentage: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False
    )
    min_order_value: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="active", index=True
    )  # active, expired, claimed
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    metadata_json: Mapped[dict | None] = mapped_column(
        "metadata", JSONB, nullable=True, default=dict
    )

    merchant = relationship("Merchant")
    action_plan = relationship("ActionPlan")
