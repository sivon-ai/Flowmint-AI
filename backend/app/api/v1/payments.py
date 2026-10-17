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
from app.schemas.store import (
    PaymentConfigResponse,
    PaymentConfigUpdateRequest,
    PaymentVerifyRequest,
)
from app.services.payment import PaymentService

router = APIRouter(prefix="/payments", tags=["Payments"])


@router.post("/{order_id}/initiate", response_model=ApiResponse[RazorpayOrderResponse])
async def initiate_payment(
    order_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
):
    """Create a Razorpay order and return checkout details to frontend."""
    service = PaymentService(db)
    result = await service.initiate(user.merchant_id, order_id, idempotency_key=idempotency_key)
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


@router.post("/verify", response_model=ApiResponse[PaymentResponse])
async def verify_payment(
    data: PaymentVerifyRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Verify Razorpay checkout response on backend.
    Enforces signature verification against saved order and advances status.
    """
    service = PaymentService(db)
    result = await service.verify_checkout(
        merchant_id=user.merchant_id,
        payment_id=data.payment_id,
        razorpay_order_id=data.razorpay_order_id,
        razorpay_payment_id=data.razorpay_payment_id,
        razorpay_signature=data.razorpay_signature,
    )
    return ApiResponse.ok(result)


@router.get("/config", response_model=ApiResponse[PaymentConfigResponse])
async def get_payment_config(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get current merchant payment configuration and gateway mode."""
    service = PaymentService(db)
    result = await service.get_payment_config(user.merchant_id)
    return ApiResponse.ok(PaymentConfigResponse(**result))


@router.post("/config", response_model=ApiResponse[PaymentConfigResponse])
async def update_payment_config(
    data: PaymentConfigUpdateRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Configure merchant payment options and Razorpay keys."""
    service = PaymentService(db)
    result = await service.update_payment_config(user.merchant_id, data.model_dump())
    return ApiResponse.ok(PaymentConfigResponse(**result))


@router.get("/{payment_id}", response_model=ApiResponse[PaymentResponse])
async def get_payment(
    payment_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = PaymentService(db)
    payment = await service.get(user.merchant_id, payment_id)
    return ApiResponse.ok(payment)

