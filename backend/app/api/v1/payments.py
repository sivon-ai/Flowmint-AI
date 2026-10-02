"""
Payment endpoints.

CRITICAL: The webhook endpoint does NOT require JWT auth.
Razorpay signature verification is the authentication mechanism.
"""

import uuid

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user
from app.database import get_db
from app.schemas.common import ApiResponse
from app.schemas.payment import PaymentResponse, RazorpayOrderResponse
from app.services.payment import PaymentService

router = APIRouter(prefix="/payments", tags=["Payments"])


@router.post("/{order_id}/initiate", response_model=ApiResponse[RazorpayOrderResponse])
async def initiate_payment(
    order_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a Razorpay order and return checkout details to frontend."""
    service = PaymentService(db)
    result = await service.initiate(user.merchant_id, order_id)
    return ApiResponse.ok(result)


@router.post("/webhook")
async def handle_webhook(
    request: Request,
    x_razorpay_signature: str = Header(..., alias="X-Razorpay-Signature"),
    db: AsyncSession = Depends(get_db),
):
    """
    Razorpay webhook receiver.

    Authentication: Razorpay HMAC signature verification (NOT JWT).
    Idempotency: Duplicate events are safely ignored.
    """
    raw_body = await request.body()
    service = PaymentService(db)
    result = await service.handle_webhook(raw_body, x_razorpay_signature)
    return result


@router.get("/{payment_id}", response_model=ApiResponse[PaymentResponse])
async def get_payment(
    payment_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = PaymentService(db)
    payment = await service.get(user.merchant_id, payment_id)
    return ApiResponse.ok(payment)
