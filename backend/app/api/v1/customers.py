"""Customer endpoints — CRUD, tenant-scoped."""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user
from app.core.exceptions import ConflictError, NotFoundError
from app.core.pagination import PaginationMeta, PaginationParams
from app.database import get_db
from app.models.customer import Customer
from app.schemas.common import ApiResponse
from app.schemas.customer import CustomerCreateRequest, CustomerResponse, CustomerUpdateRequest

router = APIRouter(prefix="/customers", tags=["Customers"])


@router.get("", response_model=ApiResponse[list[CustomerResponse]])
async def list_customers(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    pagination = PaginationParams(page=page, per_page=per_page)
    count = await db.execute(
        select(func.count()).select_from(Customer).where(
            Customer.merchant_id == user.merchant_id
        )
    )
    total = count.scalar() or 0

    result = await db.execute(
        select(Customer)
        .where(Customer.merchant_id == user.merchant_id)
        .order_by(Customer.created_at.desc())
        .offset(pagination.offset)
        .limit(pagination.per_page)
    )
    customers = result.scalars().all()
    meta = PaginationMeta.from_params(pagination, total)
    return ApiResponse.ok(
        [CustomerResponse.model_validate(c) for c in customers], meta=meta
    )


@router.post("", response_model=ApiResponse[CustomerResponse], status_code=201)
async def create_customer(
    data: CustomerCreateRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Check uniqueness
    existing = await db.execute(
        select(Customer).where(
            Customer.merchant_id == user.merchant_id,
            Customer.email == data.email,
        )
    )
    if existing.scalar_one_or_none():
        raise ConflictError(f"Customer with email '{data.email}' already exists")

    customer = Customer(
        merchant_id=user.merchant_id,
        email=data.email,
        name=data.name,
        phone=data.phone,
        metadata_json=data.metadata,
    )
    db.add(customer)
    await db.commit()
    await db.refresh(customer)
    return ApiResponse.ok(CustomerResponse.model_validate(customer))


@router.get("/{customer_id}", response_model=ApiResponse[CustomerResponse])
async def get_customer(
    customer_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Customer).where(
            Customer.id == customer_id,
            Customer.merchant_id == user.merchant_id,
        )
    )
    customer = result.scalar_one_or_none()
    if not customer:
        raise NotFoundError("Customer", str(customer_id))
    return ApiResponse.ok(CustomerResponse.model_validate(customer))
