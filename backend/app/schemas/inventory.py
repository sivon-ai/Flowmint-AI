"""Inventory schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class InventoryUpdateRequest(BaseModel):
    quantity: int | None = Field(None, ge=0)
    low_stock_threshold: int | None = Field(None, ge=0)


class InventoryResponse(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    merchant_id: uuid.UUID
    quantity: int
    reserved: int
    available: int
    low_stock_threshold: int
    is_low_stock: bool
    is_in_stock: bool
    updated_at: datetime

    model_config = {"from_attributes": True}
