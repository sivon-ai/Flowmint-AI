"""Order endpoints — create from cart, list, get."""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user
from app.core.pagination import PaginationParams
from app.database import get_db
from app.schemas.common import ApiResponse
from app.schemas.order import OrderCreateRequest, OrderResponse
from app.services.order import OrderService

router = APIRouter(prefix="/orders", tags=["Orders"])


@router.post("", response_model=ApiResponse[OrderResponse], status_code=201)
async def create_order(
    data: OrderCreateRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create an order from a cart. Reserves inventory."""
    service = OrderService(db)
    # For Phase 1, use user_id as customer_id (merchant buying as test)
    # In production, this would be the authenticated buyer's customer_id
    from app.models.customer import Customer
    from sqlalchemy import select

    # Get or create a customer for this user
    result = await db.execute(
        select(Customer).where(
            Customer.merchant_id == user.merchant_id,
        ).limit(1)
    )
    customer = result.scalar_one_or_none()
    if not customer:
        from app.core.exceptions import ValidationError
        raise ValidationError("No customer found. Create a customer first.")

    order = await service.create_from_cart(user.merchant_id, customer.id, data)
    return ApiResponse.ok(order)


@router.get("", response_model=ApiResponse[list[OrderResponse]])
async def list_orders(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = OrderService(db)
    pagination = PaginationParams(page=page, per_page=per_page)
    orders, meta = await service.list(user.merchant_id, pagination)
    return ApiResponse.ok(orders, meta=meta)


@router.get("/{order_id}", response_model=ApiResponse[OrderResponse])
async def get_order(
    order_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = OrderService(db)
    order = await service.get(user.merchant_id, order_id)
    return ApiResponse.ok(order)
