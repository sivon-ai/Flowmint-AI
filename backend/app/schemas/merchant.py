"""Merchant schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class MerchantResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    email: str
    phone: str | None
    description: str | None
    logo_url: str | None
    settings: dict | None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class MerchantUpdateRequest(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=255)
    phone: str | None = Field(None, max_length=20)
    description: str | None = None
    logo_url: str | None = None
    settings: dict | None = None
