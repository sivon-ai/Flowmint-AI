"""Product endpoints — CRUD + search, all tenant-scoped."""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user, require_role
from app.core.pagination import PaginationParams
from app.database import get_db
from app.schemas.common import ApiResponse
from app.schemas.product import (
    ProductCreateRequest,
    ProductResponse,
    ProductSearchParams,
    ProductUpdateRequest,
)
from app.services.product import ProductService

router = APIRouter(prefix="/products", tags=["Products"])


@router.get("", response_model=ApiResponse[list[ProductResponse]])
async def list_products(
    q: str | None = None,
    category_id: uuid.UUID | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    status: str | None = "active",
    sort_by: str = "created_at",
    sort_order: str = "desc",
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ProductService(db)
    search = ProductSearchParams(
        q=q, category_id=category_id, min_price=min_price, max_price=max_price,
        status=status, sort_by=sort_by, sort_order=sort_order,
    )
    pagination = PaginationParams(page=page, per_page=per_page)
    products, meta = await service.list(user.merchant_id, search, pagination)
    return ApiResponse.ok(products, meta=meta)


@router.post("", response_model=ApiResponse[ProductResponse], status_code=201)
async def create_product(
    data: ProductCreateRequest,
    user: CurrentUser = Depends(require_role("owner", "admin")),
    db: AsyncSession = Depends(get_db),
):
    service = ProductService(db)
    product = await service.create(user.merchant_id, data)
    return ApiResponse.ok(product)


@router.get("/{product_id}", response_model=ApiResponse[ProductResponse])
async def get_product(
    product_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ProductService(db)
    product = await service.get(user.merchant_id, product_id)
    return ApiResponse.ok(product)


@router.patch("/{product_id}", response_model=ApiResponse[ProductResponse])
async def update_product(
    product_id: uuid.UUID,
    data: ProductUpdateRequest,
    user: CurrentUser = Depends(require_role("owner", "admin")),
    db: AsyncSession = Depends(get_db),
):
    service = ProductService(db)
    product = await service.update(user.merchant_id, product_id, data)
    return ApiResponse.ok(product)


@router.delete("/{product_id}", status_code=204)
async def delete_product(
    product_id: uuid.UUID,
    user: CurrentUser = Depends(require_role("owner", "admin")),
    db: AsyncSession = Depends(get_db),
):
    service = ProductService(db)
    await service.delete(user.merchant_id, product_id)
