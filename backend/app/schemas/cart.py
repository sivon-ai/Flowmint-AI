"""Cart schemas."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class CartItemAddRequest(BaseModel):
    product_id: uuid.UUID
    quantity: int = Field(default=1, ge=1, le=100)


class CartItemUpdateRequest(BaseModel):
    quantity: int = Field(..., ge=1, le=100)


class CartItemResponse(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    product_name: str | None = None
    quantity: int
    unit_price: Decimal
    line_total: Decimal

    model_config = {"from_attributes": True}


class CartCreateRequest(BaseModel):
    customer_id: uuid.UUID | None = None


class CartResponse(BaseModel):
    id: uuid.UUID
    merchant_id: uuid.UUID
    customer_id: uuid.UUID | None
    status: str
    items: list[CartItemResponse]
    subtotal: Decimal
    item_count: int
    created_at: datetime

    model_config = {"from_attributes": True}
