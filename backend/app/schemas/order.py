"""Order schemas."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class OrderCreateRequest(BaseModel):
    cart_id: uuid.UUID
    shipping_address: dict | None = None
    notes: str | None = None


class OrderItemResponse(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    product_name: str
    product_sku: str
    quantity: int
    unit_price: Decimal
    total: Decimal

    model_config = {"from_attributes": True}


class OrderResponse(BaseModel):
    id: uuid.UUID
    merchant_id: uuid.UUID
    customer_id: uuid.UUID
    cart_id: uuid.UUID | None
    order_number: str
    status: str
    subtotal: Decimal
    tax: Decimal
    discount: Decimal
    total: Decimal
    currency: str
    shipping_address: dict | None
    notes: str | None
    items: list[OrderItemResponse]
    created_at: datetime

    model_config = {"from_attributes": True}
