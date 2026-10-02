"""Product schemas."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class ProductAttributeSchema(BaseModel):
    key: str = Field(..., max_length=100)
    value: str = Field(..., max_length=500)

    model_config = {"from_attributes": True}


class ProductCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=500)
    description: str | None = None
    sku: str = Field(..., min_length=1, max_length=100)
    price: Decimal = Field(..., gt=0, max_digits=12, decimal_places=2)
    compare_at_price: Decimal | None = Field(None, gt=0, max_digits=12, decimal_places=2)
    currency: str = Field(default="INR", max_length=3)
    category_id: uuid.UUID | None = None
    status: str = Field(default="active", pattern=r"^(active|draft|archived)$")
    image_url: str | None = None
    attributes: list[ProductAttributeSchema] = Field(default_factory=list)
    initial_stock: int = Field(default=0, ge=0)


class ProductUpdateRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=500)
    description: str | None = None
    price: Decimal | None = Field(None, gt=0, max_digits=12, decimal_places=2)
    compare_at_price: Decimal | None = Field(None, gt=0, max_digits=12, decimal_places=2)
    category_id: uuid.UUID | None = None
    status: str | None = Field(None, pattern=r"^(active|draft|archived)$")
    image_url: str | None = None
    attributes: list[ProductAttributeSchema] | None = None


class InventoryInfo(BaseModel):
    quantity: int
    reserved: int
    available: int
    is_low_stock: bool
    is_in_stock: bool

    model_config = {"from_attributes": True}


class ProductResponse(BaseModel):
    id: uuid.UUID
    merchant_id: uuid.UUID
    category_id: uuid.UUID | None
    name: str
    slug: str
    description: str | None
    sku: str
    price: Decimal
    compare_at_price: Decimal | None
    currency: str
    status: str
    image_url: str | None
    attributes: list[ProductAttributeSchema]
    inventory: InventoryInfo | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProductSearchParams(BaseModel):
    q: str | None = None
    category_id: uuid.UUID | None = None
    min_price: Decimal | None = None
    max_price: Decimal | None = None
    status: str | None = "active"
    in_stock: bool | None = None
    sort_by: str = Field(default="created_at", pattern=r"^(name|price|created_at)$")
    sort_order: str = Field(default="desc", pattern=r"^(asc|desc)$")
