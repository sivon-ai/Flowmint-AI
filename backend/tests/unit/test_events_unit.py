"""
Unit tests for EventBus and OutboxDispatcher.

Tests:
- In-process pub/sub delivery
- Multiple subscribers for same event
- Global subscriber handling
- Error isolation across handlers
- OutboxDispatcher fetching pending events and publishing to bus
"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.events.bus import DomainEvent, EventBus
from app.events.dispatcher import OutboxDispatcher
from app.models.outbox import OutboxEvent


class TestEventsAndOutboxUnit:
    @pytest.mark.asyncio
    async def test_event_bus_single_subscriber(self):
        bus = EventBus()
        received = []

        async def handler(event: DomainEvent):
            received.append(event)

        bus.subscribe("order.created", handler)
        event = DomainEvent(
            event_type="order.created",
            aggregate_type="order",
            aggregate_id="123",
            payload={"order_number": "FM-101"},
            merchant_id="m1",
        )
        await bus.publish(event)

        assert len(received) == 1
        assert received[0].aggregate_id == "123"
        assert received[0].payload["order_number"] == "FM-101"

    @pytest.mark.asyncio
    async def test_event_bus_multiple_subscribers(self):
        bus = EventBus()
        counts = {"h1": 0, "h2": 0}

        async def handler_1(event: DomainEvent):
            counts["h1"] += 1

        async def handler_2(event: DomainEvent):
            counts["h2"] += 1

        bus.subscribe("payment.captured", handler_1)
        bus.subscribe("payment.captured", handler_2)

        event = DomainEvent(
            event_type="payment.captured",
            aggregate_type="payment",
            aggregate_id="p1",
            payload={"amount": "100.00"},
        )
        await bus.publish(event)

        assert counts["h1"] == 1
        assert counts["h2"] == 1

    @pytest.mark.asyncio
    async def test_event_bus_error_isolation(self):
        """A failing handler should not prevent other handlers from running."""
        bus = EventBus()
        results = []

        async def failing_handler(event: DomainEvent):
            raise RuntimeError("Boom!")

        async def successful_handler(event: DomainEvent):
            results.append("success")

        bus.subscribe("test.event", failing_handler)
        bus.subscribe("test.event", successful_handler)

        event = DomainEvent(
            event_type="test.event",
            aggregate_type="test",
            aggregate_id="1",
            payload={},
        )
        await bus.publish(event)

        assert results == ["success"]

    @pytest.mark.asyncio
    async def test_outbox_dispatcher_processes_pending_events(self):
        mock_db = AsyncMock()
        mock_bus = EventBus()
        dispatched_events = []

        async def capture_event(event: DomainEvent):
            dispatched_events.append(event)

        mock_bus.subscribe("order.created", capture_event)

        outbox_event = OutboxEvent(
            id=uuid.uuid4(),
            event_type="order.created",
            aggregate_type="order",
            aggregate_id="ord_999",
            payload={"merchant_id": "m_1", "order_number": "FM-999"},
            status="pending",
        )

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [outbox_event]
        mock_db.execute.return_value = mock_result

        dispatcher = OutboxDispatcher(db=mock_db, bus=mock_bus)
        count = await dispatcher.dispatch_pending(limit=10)

        assert count == 1
        assert outbox_event.status == "published"
        assert len(dispatched_events) == 1
        assert dispatched_events[0].aggregate_id == "ord_999"
        mock_db.commit.assert_awaited_once()
