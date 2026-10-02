"""Phase 4 Revenue Attribution & AI Evaluation Benchmark Models

Revision ID: 005_phase4_attribution_evaluation
Revises: 004_phase3_safety_governance
Create Date: 2026-10-02 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '005_phase4_attribution'
down_revision: Union[str, None] = '004_phase3_safety_governance'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. action_outcomes
    op.create_table(
        'action_outcomes',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('merchant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('merchants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('action_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('action_plans.id', ondelete='CASCADE'), nullable=False),
        sa.Column('execution_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('action_executions.id', ondelete='SET NULL'), nullable=True),
        sa.Column('campaign_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('campaigns.id', ondelete='SET NULL'), nullable=True),
        sa.Column('opportunity_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('opportunities.id', ondelete='SET NULL'), nullable=True),
        sa.Column('trace_id', sa.String(100), nullable=True),
        sa.Column('label', sa.String(20), nullable=False, server_default='OBSERVED'),
        sa.Column('attribution_method', sa.String(50), nullable=False, server_default='deterministic_event'),
        sa.Column('confidence', sa.Numeric(4, 3), nullable=False, server_default='1.000'),
        sa.Column('baseline_period', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('observation_period', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('affected_entities', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('orders_attributed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('gross_revenue', sa.Numeric(12, 2), nullable=False, server_default='0.00'),
        sa.Column('discount_cost', sa.Numeric(12, 2), nullable=False, server_default='0.00'),
        sa.Column('operational_cost', sa.Numeric(12, 2), nullable=False, server_default='0.00'),
        sa.Column('net_revenue_impact', sa.Numeric(12, 2), nullable=False, server_default='0.00'),
        sa.Column('evidence_summary', sa.Text(), nullable=True),
        sa.Column('metadata_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('observed_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_action_outcomes_merchant_id', 'action_outcomes', ['merchant_id'])
    op.create_index('ix_action_outcomes_action_id', 'action_outcomes', ['action_id'])
    op.create_index('ix_action_outcomes_execution_id', 'action_outcomes', ['execution_id'])
    op.create_index('ix_action_outcomes_campaign_id', 'action_outcomes', ['campaign_id'])
    op.create_index('ix_action_outcomes_opportunity_id', 'action_outcomes', ['opportunity_id'])
    op.create_index('ix_action_outcomes_trace_id', 'action_outcomes', ['trace_id'])
    op.create_index('ix_action_outcomes_label', 'action_outcomes', ['label'])

    # 2. evaluation_benchmarks
    op.create_table(
        'evaluation_benchmarks',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('runner_type', sa.String(20), nullable=False),
        sa.Column('model_name', sa.String(100), nullable=False),
        sa.Column('dataset_version', sa.String(50), nullable=False, server_default='v1.0'),
        sa.Column('total_cases', sa.Integer(), nullable=False),
        sa.Column('passed_cases', sa.Integer(), nullable=False),
        sa.Column('intent_accuracy', sa.Numeric(5, 2), nullable=False),
        sa.Column('tool_accuracy', sa.Numeric(5, 2), nullable=False),
        sa.Column('param_accuracy', sa.Numeric(5, 2), nullable=False),
        sa.Column('grounding_rate', sa.Numeric(5, 2), nullable=False),
        sa.Column('hallucination_rate', sa.Numeric(5, 2), nullable=False),
        sa.Column('safety_pass_rate', sa.Numeric(5, 2), nullable=False),
        sa.Column('injection_resistance_rate', sa.Numeric(5, 2), nullable=False),
        sa.Column('avg_latency_ms', sa.Integer(), nullable=False),
        sa.Column('total_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('estimated_cost_usd', sa.Numeric(8, 4), nullable=False, server_default='0.0000'),
        sa.Column('results_breakdown', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_evaluation_benchmarks_runner_type', 'evaluation_benchmarks', ['runner_type'])


def downgrade() -> None:
    op.drop_table('evaluation_benchmarks')
    op.drop_table('action_outcomes')
