"""Cart endpoints — create, add/update/remove items."""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user
from app.database import get_db
from app.schemas.cart import CartCreateRequest, CartItemAddRequest, CartItemUpdateRequest, CartResponse
from app.schemas.common import ApiResponse
from app.services.cart import CartService

router = APIRouter(prefix="/carts", tags=["Carts"])


@router.post("", response_model=ApiResponse[CartResponse], status_code=201)
async def create_cart(
    data: CartCreateRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = CartService(db)
    cart = await service.create(user.merchant_id, data)
    return ApiResponse.ok(cart)


@router.get("/{cart_id}", response_model=ApiResponse[CartResponse])
async def get_cart(
    cart_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = CartService(db)
    cart = await service.get(user.merchant_id, cart_id)
    return ApiResponse.ok(cart)


@router.post("/{cart_id}/items", response_model=ApiResponse[CartResponse])
async def add_cart_item(
    cart_id: uuid.UUID,
    data: CartItemAddRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = CartService(db)
    cart = await service.add_item(user.merchant_id, cart_id, data)
    return ApiResponse.ok(cart)


@router.patch("/{cart_id}/items/{item_id}", response_model=ApiResponse[CartResponse])
async def update_cart_item(
    cart_id: uuid.UUID,
    item_id: uuid.UUID,
    data: CartItemUpdateRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = CartService(db)
    cart = await service.update_item(user.merchant_id, cart_id, item_id, data)
    return ApiResponse.ok(cart)


@router.delete("/{cart_id}/items/{item_id}", response_model=ApiResponse[CartResponse])
async def remove_cart_item(
    cart_id: uuid.UUID,
    item_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = CartService(db)
    cart = await service.remove_item(user.merchant_id, cart_id, item_id)
    return ApiResponse.ok(cart)
