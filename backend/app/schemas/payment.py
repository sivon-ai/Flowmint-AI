"""Payment schemas."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class PaymentInitiateRequest(BaseModel):
    """Initiate a Razorpay payment for an order."""
    pass  # order_id comes from URL path


class PaymentResponse(BaseModel):
    id: uuid.UUID
    order_id: uuid.UUID
    merchant_id: uuid.UUID
    amount: Decimal
    currency: str
    status: str
    provider: str
    provider_order_id: str | None
    provider_payment_id: str | None
    failure_reason: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class RazorpayOrderResponse(BaseModel):
    """Response containing Razorpay order details for frontend checkout."""
    payment_id: uuid.UUID
    razorpay_order_id: str
    razorpay_key_id: str
    amount: int  # in paise
    currency: str
    order_number: str
    merchant_name: str


class PaymentVerifyRequest(BaseModel):
    """Frontend sends this after Razorpay checkout success (backup only — webhook is authoritative)."""
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str
