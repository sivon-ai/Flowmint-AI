"""Phase 3 Safety, Governance, Policy, Approval, Execution & Audit Models

Revision ID: 004_phase3_safety_governance
Revises: 003_phase2b_revenue_engine
Create Date: 2026-10-02 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '004_phase3_safety_governance'
down_revision: Union[str, None] = '003_phase2b_revenue_engine'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. merchant_policies
    op.create_table(
        'merchant_policies',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('merchant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('merchants.id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('max_discount_percentage', sa.Numeric(5, 2), nullable=False, server_default='15.00'),
        sa.Column('max_campaign_budget', sa.Numeric(12, 2), nullable=False, server_default='50000.00'),
        sa.Column('high_value_threshold', sa.Numeric(12, 2), nullable=False, server_default='10000.00'),
        sa.Column('contact_cooldown_hours', sa.Integer(), nullable=False, server_default='24'),
        sa.Column('require_approval_all_actions', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('auto_approval_max_risk', sa.String(20), nullable=False, server_default='low'),
        sa.Column('allowed_action_types', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='["abandoned_cart_recovery", "cross_sell_bundle", "promotional_offer", "payment_retry_nudge"]'),
        sa.Column('restricted_product_ids', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='[]'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_merchant_policies_merchant_id', 'merchant_policies', ['merchant_id'])

    # 2. approvals
    op.create_table(
        'approvals',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('merchant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('merchants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('action_plan_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('action_plans.id', ondelete='CASCADE'), nullable=False),
        sa.Column('requested_by', sa.String(50), nullable=False, server_default='growth_agent'),
        sa.Column('risk_level', sa.String(20), nullable=False, server_default='medium'),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('status', sa.String(50), nullable=False, server_default='pending'),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('decided_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('decided_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('decision_reason', sa.Text(), nullable=True),
        sa.Column('policy_snapshot', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_approvals_merchant_id', 'approvals', ['merchant_id'])
    op.create_index('ix_approvals_action_plan_id', 'approvals', ['action_plan_id'])
    op.create_index('ix_approvals_status', 'approvals', ['status'])

    # 3. action_executions
    op.create_table(
        'action_executions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('merchant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('merchants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('action_plan_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('action_plans.id', ondelete='CASCADE'), nullable=False),
        sa.Column('idempotency_key', sa.String(255), nullable=False),
        sa.Column('status', sa.String(50), nullable=False, server_default='executing'),
        sa.Column('tool_name', sa.String(100), nullable=False),
        sa.Column('tool_parameters', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('tool_result', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint('merchant_id', 'idempotency_key', name='uq_merchant_idempotency_key'),
    )
    op.create_index('ix_action_executions_merchant_id', 'action_executions', ['merchant_id'])
    op.create_index('ix_action_executions_action_plan_id', 'action_executions', ['action_plan_id'])
    op.create_index('ix_action_executions_idempotency_key', 'action_executions', ['idempotency_key'])
    op.create_index('ix_action_executions_status', 'action_executions', ['status'])

    # 4. audit_logs
    op.create_table(
        'audit_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('merchant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('merchants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('event_id', sa.String(100), nullable=False, unique=True),
        sa.Column('actor_type', sa.String(50), nullable=False),
        sa.Column('actor_id', sa.String(100), nullable=False),
        sa.Column('action_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('action_plans.id', ondelete='SET NULL'), nullable=True),
        sa.Column('agent', sa.String(50), nullable=True),
        sa.Column('event_type', sa.String(100), nullable=False),
        sa.Column('previous_status', sa.String(50), nullable=True),
        sa.Column('new_status', sa.String(50), nullable=True),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('policy_results', postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default='{}'),
        sa.Column('approval_result', postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default='{}'),
        sa.Column('execution_result', postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default='{}'),
        sa.Column('trace_id', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_audit_logs_merchant_id', 'audit_logs', ['merchant_id'])
    op.create_index('ix_audit_logs_event_id', 'audit_logs', ['event_id'])
    op.create_index('ix_audit_logs_actor_type', 'audit_logs', ['actor_type'])
    op.create_index('ix_audit_logs_actor_id', 'audit_logs', ['actor_id'])
    op.create_index('ix_audit_logs_action_id', 'audit_logs', ['action_id'])
    op.create_index('ix_audit_logs_event_type', 'audit_logs', ['event_type'])
    op.create_index('ix_audit_logs_trace_id', 'audit_logs', ['trace_id'])
    op.create_index('ix_audit_logs_created_at', 'audit_logs', ['created_at'])

    # 5. campaigns
    op.create_table(
        'campaigns',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('merchant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('merchants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('action_plan_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('action_plans.id', ondelete='SET NULL'), nullable=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('type', sa.String(50), nullable=False),
        sa.Column('status', sa.String(50), nullable=False, server_default='draft'),
        sa.Column('discount_percentage', sa.Numeric(5, 2), nullable=False, server_default='0.00'),
        sa.Column('target_criteria', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('budget', sa.Numeric(12, 2), nullable=False, server_default='0.00'),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_campaigns_merchant_id', 'campaigns', ['merchant_id'])
    op.create_index('ix_campaigns_action_plan_id', 'campaigns', ['action_plan_id'])
    op.create_index('ix_campaigns_type', 'campaigns', ['type'])
    op.create_index('ix_campaigns_status', 'campaigns', ['status'])

    # 6. offers
    op.create_table(
        'offers',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('merchant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('merchants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('action_plan_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('action_plans.id', ondelete='SET NULL'), nullable=True),
        sa.Column('code', sa.String(50), nullable=False),
        sa.Column('discount_percentage', sa.Numeric(5, 2), nullable=False),
        sa.Column('min_order_value', sa.Numeric(12, 2), nullable=False, server_default='0.00'),
        sa.Column('status', sa.String(50), nullable=False, server_default='active'),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_offers_merchant_id', 'offers', ['merchant_id'])
    op.create_index('ix_offers_action_plan_id', 'offers', ['action_plan_id'])
    op.create_index('ix_offers_code', 'offers', ['code'])
    op.create_index('ix_offers_status', 'offers', ['status'])


def downgrade() -> None:
    op.drop_table('offers')
    op.drop_table('campaigns')
    op.drop_table('audit_logs')
    op.drop_table('action_executions')
    op.drop_table('approvals')
    op.drop_table('merchant_policies')
