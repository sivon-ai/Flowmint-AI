"""
Flowmint AI — Phase 4 Revenue Attribution & AI Evaluation Models.

Models:
- ActionOutcome: Records measured and attributed financial outcomes from executed actions.
- EvaluationBenchmark: Records fixed AI benchmark runs and test suite metrics.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, generate_uuid


class AttributionLabel(str, enum.Enum):
    SIMULATED = "SIMULATED"
    ESTIMATED = "ESTIMATED"
    OBSERVED = "OBSERVED"
    ATTRIBUTED = "ATTRIBUTED"


class AttributionMethod(str, enum.Enum):
    DETERMINISTIC_EVENT = "deterministic_event"
    RULE_BASED = "rule_based"
    DIFFERENCE_IN_DIFFERENCES = "difference_in_differences"
    COHORT_ANALYSIS = "cohort_analysis"


class ActionOutcome(TimestampMixin, Base):
    """
    Measurable financial outcome attributed to an executed ActionPlan.
    Clearly distinguishes SIMULATED, ESTIMATED, OBSERVED, and ATTRIBUTED figures.
    """

    __tablename__ = "action_outcomes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    merchant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("merchants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    action_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("action_plans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    execution_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("action_executions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("campaigns.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    opportunity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("opportunities.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    trace_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)

    # Attribution Classification & Method
    label: Mapped[str] = mapped_column(
        String(20), default=AttributionLabel.OBSERVED.value, nullable=False, index=True
    )
    attribution_method: Mapped[str] = mapped_column(
        String(50), default=AttributionMethod.DETERMINISTIC_EVENT.value, nullable=False
    )
    confidence: Mapped[Decimal] = mapped_column(
        Numeric(4, 3), default=Decimal("1.000"), nullable=False
    )

    # Time Windows & Cohorts
    baseline_period: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    observation_period: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    affected_entities: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    # Quantified Attribution Metrics
    orders_attributed: Mapped[int] = mapped_column(default=0, nullable=False)
    gross_revenue: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00"), nullable=False
    )
    discount_cost: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00"), nullable=False
    )
    operational_cost: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00"), nullable=False
    )
    net_revenue_impact: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00"), nullable=False
    )

    # Notes & Evidentiary breakdown
    evidence_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    merchant = relationship("Merchant")
    action_plan = relationship("ActionPlan")
    execution = relationship("ActionExecution")
    campaign = relationship("Campaign")


class EvaluationBenchmark(TimestampMixin, Base):
    """
    Fixed dataset AI evaluation benchmark run.
    Separates MockLLM regression runs from Real LLM live evaluations.
    """

    __tablename__ = "evaluation_benchmarks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    runner_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)  # "mock_llm" | "real_llm"
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    dataset_version: Mapped[str] = mapped_column(String(50), nullable=False, default="v1.0")

    total_cases: Mapped[int] = mapped_column(nullable=False)
    passed_cases: Mapped[int] = mapped_column(nullable=False)

    # Detailed Accuracy Metrics (Percentages 0.00 to 100.00)
    intent_accuracy: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    tool_accuracy: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    param_accuracy: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    grounding_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    hallucination_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    safety_pass_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    injection_resistance_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)

    # Performance & Cost Telemetry
    avg_latency_ms: Mapped[int] = mapped_column(nullable=False)
    total_tokens: Mapped[int] = mapped_column(nullable=False, default=0)
    estimated_cost_usd: Mapped[Decimal] = mapped_column(
        Numeric(8, 4), default=Decimal("0.0000"), nullable=False
    )

    results_breakdown: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
