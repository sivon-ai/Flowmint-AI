"""Phase 2B Revenue Engine: opportunities, action_plans, simulation_records

Revision ID: 003_phase2b_revenue_engine
Revises: 002_phase2a_ai_models
Create Date: 2026-10-02 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '003_phase2b_revenue_engine'
down_revision: Union[str, None] = '002_phase2a_ai_models'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. opportunities
    op.create_table(
        'opportunities',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('merchant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('merchants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('type', sa.String(length=50), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='detected'),
        sa.Column('priority', sa.String(length=20), nullable=False, server_default='medium'),
        sa.Column('confidence', sa.Numeric(precision=3, scale=2), nullable=False, server_default='0.85'),
        sa.Column('estimated_value', sa.Numeric(precision=12, scale=2), nullable=False, server_default='0.00'),
        sa.Column('currency', sa.String(length=3), nullable=False, server_default='INR'),
        sa.Column('evidence', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('affected_entity_type', sa.String(length=50), nullable=False, server_default='cart'),
        sa.Column('affected_entity_ids', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='[]'),
        sa.Column('recommended_action', sa.Text(), nullable=True),
        sa.Column('detected_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_opportunities_merchant_id', 'opportunities', ['merchant_id'])
    op.create_index('ix_opportunities_type', 'opportunities', ['type'])
    op.create_index('ix_opportunities_status', 'opportunities', ['status'])

    # 2. action_plans
    op.create_table(
        'action_plans',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('merchant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('merchants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('opportunity_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('opportunities.id', ondelete='SET NULL'), nullable=True),
        sa.Column('action_type', sa.String(length=50), nullable=False),
        sa.Column('target', sa.String(length=100), nullable=False),
        sa.Column('parameters', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('evidence', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('recommendation_reason', sa.Text(), nullable=False),
        sa.Column('estimated_impact', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('risk_level', sa.String(length=20), nullable=False, server_default='medium'),
        sa.Column('requires_approval', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='proposed'),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_action_plans_merchant_id', 'action_plans', ['merchant_id'])
    op.create_index('ix_action_plans_opportunity_id', 'action_plans', ['opportunity_id'])
    op.create_index('ix_action_plans_action_type', 'action_plans', ['action_type'])
    op.create_index('ix_action_plans_status', 'action_plans', ['status'])

    # 3. simulation_records
    op.create_table(
        'simulation_records',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('merchant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('merchants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('opportunity_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('opportunities.id', ondelete='SET NULL'), nullable=True),
        sa.Column('action_plan_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('action_plans.id', ondelete='SET NULL'), nullable=True),
        sa.Column('simulation_type', sa.String(length=50), nullable=False),
        sa.Column('parameters', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('results', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('assumptions', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('confidence_score', sa.Numeric(precision=3, scale=2), nullable=False, server_default='0.80'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_simulation_records_merchant_id', 'simulation_records', ['merchant_id'])
    op.create_index('ix_simulation_records_opportunity_id', 'simulation_records', ['opportunity_id'])
    op.create_index('ix_simulation_records_action_plan_id', 'simulation_records', ['action_plan_id'])
    op.create_index('ix_simulation_records_simulation_type', 'simulation_records', ['simulation_type'])


def downgrade() -> None:
    op.drop_table('simulation_records')
    op.drop_table('action_plans')
    op.drop_table('opportunities')
