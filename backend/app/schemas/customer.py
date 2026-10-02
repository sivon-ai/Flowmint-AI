"""Customer schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class CustomerCreateRequest(BaseModel):
    email: EmailStr
    name: str = Field(..., min_length=1, max_length=255)
    phone: str | None = Field(None, max_length=20)
    metadata: dict | None = None


class CustomerUpdateRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    phone: str | None = Field(None, max_length=20)
    metadata: dict | None = None


class CustomerResponse(BaseModel):
    id: uuid.UUID
    merchant_id: uuid.UUID
    email: str
    name: str
    phone: str | None
    metadata_json: dict | None = Field(None, alias="metadata_json")
    created_at: datetime

    model_config = {"from_attributes": True, "populate_by_name": True}
