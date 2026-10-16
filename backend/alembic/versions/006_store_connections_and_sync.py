"""Store connections, sync jobs, and entity mappings

Revision ID: 006_store_connections_and_sync
Revises: 005_phase4_attribution
Create Date: 2026-10-16 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '006_store_connections_and_sync'
down_revision: Union[str, None] = '005_phase4_attribution'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. store_connections
    op.create_table(
        'store_connections',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('merchant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('merchants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('provider', sa.String(50), nullable=False),
        sa.Column('store_url', sa.String(500), nullable=False),
        sa.Column('store_name', sa.String(255), nullable=True),
        sa.Column('external_store_id', sa.String(255), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, server_default='connected'),
        sa.Column('scopes', sa.String(500), nullable=True),
        sa.Column('encrypted_credentials', sa.Text(), nullable=False),
        sa.Column('sync_status', sa.String(50), nullable=False, server_default='idle'),
        sa.Column('last_sync_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('sync_summary', postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default='{}'),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('disconnected_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('merchant_id', 'provider', name='uq_store_conn_merchant_provider'),
    )
    op.create_index('ix_store_connections_merchant_id', 'store_connections', ['merchant_id'])
    op.create_index('ix_store_conn_merchant_status', 'store_connections', ['merchant_id', 'status'])

    # 2. store_sync_jobs
    op.create_table(
        'store_sync_jobs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('merchant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('merchants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('connection_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('store_connections.id', ondelete='CASCADE'), nullable=False),
        sa.Column('status', sa.String(50), nullable=False, server_default='queued'),
        sa.Column('entity_type', sa.String(50), nullable=False, server_default='all'),
        sa.Column('records_processed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('records_failed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('summary_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default='{}'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_store_sync_job_merchant', 'store_sync_jobs', ['merchant_id'])
    op.create_index('ix_store_sync_job_connection', 'store_sync_jobs', ['connection_id'])

    # 3. store_entity_mappings
    op.create_table(
        'store_entity_mappings',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('merchant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('merchants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('connection_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('store_connections.id', ondelete='CASCADE'), nullable=False),
        sa.Column('entity_type', sa.String(50), nullable=False),
        sa.Column('external_id', sa.String(255), nullable=False),
        sa.Column('internal_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('merchant_id', 'connection_id', 'entity_type', 'external_id', name='uq_store_entity_mapping'),
    )
    op.create_index('ix_store_mapping_lookup', 'store_entity_mappings', ['merchant_id', 'connection_id', 'entity_type'])


def downgrade() -> None:
    op.drop_table('store_entity_mappings')
    op.drop_table('store_sync_jobs')
    op.drop_table('store_connections')
