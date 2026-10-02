"""
In-process event bus for Phase 1.

Simple pub/sub pattern. Handlers are registered at startup.
Events are dispatched synchronously after outbox commit.

Migration path to Redis Streams:
- Replace dispatch() with a Redis producer
- Replace handler invocation with Redis consumer
- Keep handler signatures unchanged
"""

import logging
from collections import defaultdict
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

EventHandler = Callable[["DomainEvent"], Coroutine[Any, Any, None]]


@dataclass
class DomainEvent:
    """A domain event that represents something that happened in the system."""

    event_type: str
    aggregate_type: str
    aggregate_id: str
    payload: dict
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    merchant_id: str | None = None


class EventBus:
    """
    In-process event bus using async handlers.

    Usage:
        bus = EventBus()
        bus.subscribe("order.created", handle_order_created)
        await bus.publish(event)
    """

    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)
        self._global_handlers: list[EventHandler] = []

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """Subscribe a handler to a specific event type."""
        self._handlers[event_type].append(handler)
        logger.info(f"Handler {handler.__name__} subscribed to {event_type}")

    def subscribe_all(self, handler: EventHandler) -> None:
        """Subscribe a handler to all events."""
        self._global_handlers.append(handler)

    async def publish(self, event: DomainEvent) -> None:
        """Publish an event to all subscribed handlers."""
        handlers = self._handlers.get(event.event_type, []) + self._global_handlers
        for handler in handlers:
            try:
                await handler(event)
            except Exception:
                logger.exception(
                    f"Error in event handler {handler.__name__} for {event.event_type}"
                )


# Singleton event bus instance
event_bus = EventBus()
