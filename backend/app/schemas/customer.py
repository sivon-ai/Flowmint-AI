import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, EmailStr, Field

from app.schemas.order import OrderResponse


class CustomerCreateRequest(BaseModel):
    email: EmailStr
    name: str = Field(..., min_length=1, max_length=255)
    phone: str | None = Field(None, max_length=20)
    metadata: dict | None = None


class CustomerUpdateRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    email: EmailStr | None = None
    phone: str | None = Field(None, max_length=20)
    metadata: dict | None = None


class CustomerResponse(BaseModel):
    id: uuid.UUID
    merchant_id: uuid.UUID
    email: str
    name: str
    phone: str | None
    metadata_json: dict | None = Field(None, alias="metadata_json")
    order_count: int = 0
    total_spent: Decimal = Decimal("0.00")
    created_at: datetime
    updated_at: datetime | None = None

    model_config = {"from_attributes": True, "populate_by_name": True}


class CustomerPurchaseSummary(BaseModel):
    total_orders: int = 0
    total_spent: Decimal = Decimal("0.00")
    last_order_date: datetime | None = None
    average_order_value: Decimal = Decimal("0.00")


class CustomerOrdersResponse(BaseModel):
    customer_id: uuid.UUID
    summary: CustomerPurchaseSummary
    orders: list[OrderResponse]

