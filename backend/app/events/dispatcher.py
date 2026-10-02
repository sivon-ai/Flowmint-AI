"""
Outbox Dispatcher — processes pending OutboxEvents.

Reads pending OutboxEvents from the database in transactional order,
publishes them to the in-process EventBus, and updates their status
to 'published' (or 'failed' on unhandled error).
"""

import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.events.bus import DomainEvent, EventBus, event_bus
from app.models.outbox import OutboxEvent

logger = logging.getLogger(__name__)


class OutboxDispatcher:
    def __init__(self, db: AsyncSession, bus: EventBus = event_bus):
        self.db = db
        self.bus = bus

    async def dispatch_pending(self, limit: int = 50) -> int:
        """
        Fetch pending events, publish to event bus, and update status.
        Returns the number of dispatched events.
        """
        result = await self.db.execute(
            select(OutboxEvent)
            .where(OutboxEvent.status == "pending")
            .order_by(OutboxEvent.created_at.asc())
            .limit(limit)
        )
        events = result.scalars().all()
        dispatched_count = 0

        for event in events:
            try:
                domain_event = DomainEvent(
                    event_type=event.event_type,
                    aggregate_type=event.aggregate_type,
                    aggregate_id=event.aggregate_id,
                    payload=event.payload or {},
                    merchant_id=event.payload.get("merchant_id") if isinstance(event.payload, dict) else None,
                )
                await self.bus.publish(domain_event)
                event.status = "published"
                event.error = None
                dispatched_count += 1
            except Exception as e:
                logger.exception(f"Failed to dispatch outbox event {event.id}: {e}")
                event.status = "failed"
                event.error = str(e)

        if events:
            await self.db.commit()

        return dispatched_count
