"""
StoreConnection, StoreSyncJob, and StoreEntityMapping models.

Multi-tenant constraints:
- UNIQUE(merchant_id, provider)
- UNIQUE(merchant_id, connection_id, entity_type, external_id)
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, generate_uuid


class StoreConnection(TimestampMixin, Base):
    __tablename__ = "store_connections"
    __table_args__ = (
        UniqueConstraint("merchant_id", "provider", name="uq_store_conn_merchant_provider"),
        Index("ix_store_conn_merchant_status", "merchant_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    merchant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("merchants.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False)  # shopify, woocommerce, custom
    store_url: Mapped[str] = mapped_column(String(500), nullable=False)
    store_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    external_store_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="connected"
    )  # connected, needs_configuration, syncing, synced, error, disconnected
    scopes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    encrypted_credentials: Mapped[str] = mapped_column(Text, nullable=False)
    sync_status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="idle"
    )  # idle, running, completed, failed
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sync_summary: Mapped[dict | None] = mapped_column(JSONB, nullable=True, default=dict)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    disconnected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    merchant = relationship("Merchant", backref="store_connections")
    sync_jobs = relationship("StoreSyncJob", back_populates="connection", cascade="all, delete-orphan", lazy="noload")
    entity_mappings = relationship("StoreEntityMapping", back_populates="connection", cascade="all, delete-orphan", lazy="noload")


class StoreSyncJob(TimestampMixin, Base):
    __tablename__ = "store_sync_jobs"
    __table_args__ = (
        Index("ix_store_sync_job_merchant", "merchant_id"),
        Index("ix_store_sync_job_connection", "connection_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    merchant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("merchants.id", ondelete="CASCADE"),
        nullable=False,
    )
    connection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("store_connections.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="queued"
    )  # queued, running, completed, failed
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, default="all")
    records_processed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    summary_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    connection = relationship("StoreConnection", back_populates="sync_jobs")


class StoreEntityMapping(TimestampMixin, Base):
    __tablename__ = "store_entity_mappings"
    __table_args__ = (
        UniqueConstraint("merchant_id", "connection_id", "entity_type", "external_id", name="uq_store_entity_mapping"),
        Index("ix_store_mapping_lookup", "merchant_id", "connection_id", "entity_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    merchant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("merchants.id", ondelete="CASCADE"),
        nullable=False,
    )
    connection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("store_connections.id", ondelete="CASCADE"),
        nullable=False,
    )
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)  # product, customer, order
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    internal_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    # Relationships
    connection = relationship("StoreConnection", back_populates="entity_mappings")
