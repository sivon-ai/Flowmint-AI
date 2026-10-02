"""Inventory endpoints — stock management, tenant-scoped."""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user, require_role
from app.database import get_db
from app.schemas.common import ApiResponse
from app.schemas.inventory import InventoryResponse, InventoryUpdateRequest
from app.services.inventory import InventoryService

router = APIRouter(prefix="/inventory", tags=["Inventory"])


@router.get("", response_model=ApiResponse[list[InventoryResponse]])
async def list_inventory(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = InventoryService(db)
    items = await service.list_for_merchant(user.merchant_id)
    return ApiResponse.ok(items)


@router.get("/{product_id}", response_model=ApiResponse[InventoryResponse])
async def get_inventory(
    product_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = InventoryService(db)
    inv = await service.get(user.merchant_id, product_id)
    return ApiResponse.ok(inv)


@router.patch("/{product_id}", response_model=ApiResponse[InventoryResponse])
async def update_inventory(
    product_id: uuid.UUID,
    data: InventoryUpdateRequest,
    user: CurrentUser = Depends(require_role("owner", "admin")),
    db: AsyncSession = Depends(get_db),
):
    service = InventoryService(db)
    inv = await service.update(user.merchant_id, product_id, data)
    return ApiResponse.ok(inv)
