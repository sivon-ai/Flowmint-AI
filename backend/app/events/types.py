"""
Domain event types for Flowmint AI.

These represent business events that flow through the event bus.
The event type strings are stable contracts — do not change them
without updating all consumers.
"""

from enum import StrEnum


class EventType(StrEnum):
    # Commerce
    ORDER_CREATED = "order.created"
    ORDER_CONFIRMED = "order.confirmed"
    ORDER_COMPLETED = "order.completed"
    ORDER_CANCELLED = "order.cancelled"

    CART_CREATED = "cart.created"
    CART_UPDATED = "cart.updated"
    CART_ABANDONED = "cart.abandoned"

    PAYMENT_CREATED = "payment.created"
    PAYMENT_AUTHORIZED = "payment.authorized"
    PAYMENT_CAPTURED = "payment.captured"
    PAYMENT_FAILED = "payment.failed"
    PAYMENT_REFUNDED = "payment.refunded"

    INVENTORY_UPDATED = "inventory.updated"
    INVENTORY_LOW = "inventory.low"
    INVENTORY_RESERVED = "inventory.reserved"

    PRODUCT_CREATED = "product.created"
    PRODUCT_UPDATED = "product.updated"

    CUSTOMER_CREATED = "customer.created"
