"""Customer endpoints — CRUD, search, updates, and purchase history (tenant-scoped)."""

import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, get_current_user
from app.core.exceptions import ConflictError, NotFoundError
from app.core.pagination import PaginationMeta, PaginationParams
from app.database import get_db
from app.models.customer import Customer
from app.models.order import Order
from app.schemas.common import ApiResponse
from app.schemas.customer import (
    CustomerCreateRequest,
    CustomerOrdersResponse,
    CustomerPurchaseSummary,
    CustomerResponse,
    CustomerUpdateRequest,
)
from app.schemas.order import OrderResponse

router = APIRouter(prefix="/customers", tags=["Customers"])


@router.get("", response_model=ApiResponse[list[CustomerResponse]])
async def list_customers(
    q: str | None = None,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List customers with pagination, real purchase aggregations, and partial search.
    Tenant-scoped to authenticated merchant.
    """
    pagination = PaginationParams(page=page, per_page=per_page)

    # Base filter condition
    filter_clauses = [Customer.merchant_id == user.merchant_id]
    if q and q.strip():
        term = f"%{q.strip()}%"
        filter_clauses.append(
            or_(
                Customer.name.ilike(term),
                Customer.email.ilike(term),
                Customer.phone.ilike(term),
            )
        )

    # Count total matching
    count_stmt = select(func.count()).select_from(Customer).where(*filter_clauses)
    total = (await db.execute(count_stmt)).scalar() or 0

    # Aggregate qualifying orders (non-cancelled) per customer
    order_stats = (
        select(
            Order.customer_id,
            func.count(Order.id).label("order_count"),
            func.coalesce(func.sum(Order.total), Decimal("0.00")).label("total_spent"),
        )
        .where(
            Order.merchant_id == user.merchant_id,
            Order.status != "cancelled",
        )
        .group_by(Order.customer_id)
        .subquery()
    )

    # Query customers with aggregated order statistics
    stmt = (
        select(
            Customer,
            func.coalesce(order_stats.c.order_count, 0).label("order_count"),
            func.coalesce(order_stats.c.total_spent, Decimal("0.00")).label("total_spent"),
        )
        .outerjoin(order_stats, Customer.id == order_stats.c.customer_id)
        .where(*filter_clauses)
        .order_by(Customer.created_at.desc())
        .offset(pagination.offset)
        .limit(pagination.per_page)
    )

    result = await db.execute(stmt)
    rows = result.all()

    items: list[CustomerResponse] = []
    for c, order_count, total_spent in rows:
        items.append(
            CustomerResponse(
                id=c.id,
                merchant_id=c.merchant_id,
                email=c.email,
                name=c.name,
                phone=c.phone,
                metadata_json=c.metadata_json,
                order_count=int(order_count),
                total_spent=round(Decimal(str(total_spent)), 2),
                created_at=c.created_at,
                updated_at=c.updated_at,
            )
        )

    meta = PaginationMeta.from_params(pagination, total)
    return ApiResponse.ok(items, meta=meta)


@router.post("", response_model=ApiResponse[CustomerResponse], status_code=201)
async def create_customer(
    data: CustomerCreateRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new customer under the authenticated merchant account."""
    existing = await db.execute(
        select(Customer).where(
            Customer.merchant_id == user.merchant_id,
            Customer.email == data.email.lower().strip(),
        )
    )
    if existing.scalar_one_or_none():
        raise ConflictError(f"Customer with email '{data.email}' already exists")

    customer = Customer(
        merchant_id=user.merchant_id,
        email=data.email.lower().strip(),
        name=data.name.strip(),
        phone=data.phone.strip() if data.phone else None,
        metadata_json=data.metadata or {},
    )
    db.add(customer)
    await db.commit()
    await db.refresh(customer)

    return ApiResponse.ok(
        CustomerResponse(
            id=customer.id,
            merchant_id=customer.merchant_id,
            email=customer.email,
            name=customer.name,
            phone=customer.phone,
            metadata_json=customer.metadata_json,
            order_count=0,
            total_spent=Decimal("0.00"),
            created_at=customer.created_at,
            updated_at=customer.updated_at,
        )
    )


@router.get("/{customer_id}", response_model=ApiResponse[CustomerResponse])
async def get_customer(
    customer_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve an individual customer profile with real purchase statistics."""
    result = await db.execute(
        select(Customer).where(
            Customer.id == customer_id,
            Customer.merchant_id == user.merchant_id,
        )
    )
    customer = result.scalar_one_or_none()
    if not customer:
        raise NotFoundError("Customer", str(customer_id))

    # Calculate real order metrics
    stats_stmt = (
        select(
            func.count(Order.id).label("order_count"),
            func.coalesce(func.sum(Order.total), Decimal("0.00")).label("total_spent"),
        )
        .where(
            Order.merchant_id == user.merchant_id,
            Order.customer_id == customer_id,
            Order.status != "cancelled",
        )
    )
    stats_row = (await db.execute(stats_stmt)).one_or_none()
    order_count = int(stats_row[0]) if stats_row else 0
    total_spent = round(Decimal(str(stats_row[1])), 2) if stats_row else Decimal("0.00")

    return ApiResponse.ok(
        CustomerResponse(
            id=customer.id,
            merchant_id=customer.merchant_id,
            email=customer.email,
            name=customer.name,
            phone=customer.phone,
            metadata_json=customer.metadata_json,
            order_count=order_count,
            total_spent=total_spent,
            created_at=customer.created_at,
            updated_at=customer.updated_at,
        )
    )


@router.patch("/{customer_id}", response_model=ApiResponse[CustomerResponse])
async def update_customer(
    customer_id: uuid.UUID,
    data: CustomerUpdateRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update customer details scoped to authenticated merchant."""
    result = await db.execute(
        select(Customer).where(
            Customer.id == customer_id,
            Customer.merchant_id == user.merchant_id,
        )
    )
    customer = result.scalar_one_or_none()
    if not customer:
        raise NotFoundError("Customer", str(customer_id))

    # If email is modified, verify uniqueness within merchant
    if data.email:
        clean_email = data.email.lower().strip()
        if clean_email != customer.email.lower():
            conflict = await db.execute(
                select(Customer.id).where(
                    Customer.merchant_id == user.merchant_id,
                    Customer.email == clean_email,
                    Customer.id != customer_id,
                )
            )
            if conflict.scalar_one_or_none():
                raise ConflictError(f"Customer with email '{data.email}' already exists")
            customer.email = clean_email

    if data.name is not None and data.name.strip():
        customer.name = data.name.strip()

    if data.phone is not None:
        customer.phone = data.phone.strip() if data.phone.strip() else None

    if data.metadata is not None:
        customer.metadata_json = data.metadata

    await db.commit()
    await db.refresh(customer)

    # Fetch stats
    stats_stmt = (
        select(
            func.count(Order.id).label("order_count"),
            func.coalesce(func.sum(Order.total), Decimal("0.00")).label("total_spent"),
        )
        .where(
            Order.merchant_id == user.merchant_id,
            Order.customer_id == customer_id,
            Order.status != "cancelled",
        )
    )
    stats_row = (await db.execute(stats_stmt)).one_or_none()
    order_count = int(stats_row[0]) if stats_row else 0
    total_spent = round(Decimal(str(stats_row[1])), 2) if stats_row else Decimal("0.00")

    return ApiResponse.ok(
        CustomerResponse(
            id=customer.id,
            merchant_id=customer.merchant_id,
            email=customer.email,
            name=customer.name,
            phone=customer.phone,
            metadata_json=customer.metadata_json,
            order_count=order_count,
            total_spent=total_spent,
            created_at=customer.created_at,
            updated_at=customer.updated_at,
        )
    )


@router.get("/{customer_id}/orders", response_model=ApiResponse[CustomerOrdersResponse])
async def get_customer_orders(
    customer_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve real purchase history and derived summaries for a customer.
    Scoped strictly to authenticated merchant and verified customer ownership.
    """
    # Verify customer exists and belongs to merchant
    cust_res = await db.execute(
        select(Customer.id).where(
            Customer.id == customer_id,
            Customer.merchant_id == user.merchant_id,
        )
    )
    if not cust_res.scalar_one_or_none():
        raise NotFoundError("Customer", str(customer_id))

    # Fetch customer orders with items
    order_stmt = (
        select(Order)
        .options(selectinload(Order.items))
        .where(
            Order.merchant_id == user.merchant_id,
            Order.customer_id == customer_id,
        )
        .order_by(Order.created_at.desc())
    )
    orders = (await db.execute(order_stmt)).scalars().all()

    # Calculate real derived purchase summary
    qualifying_orders = [o for o in orders if o.status != "cancelled"]
    total_orders = len(qualifying_orders)
    total_spent = sum((o.total for o in qualifying_orders), Decimal("0.00"))
    last_order_date = qualifying_orders[0].created_at if qualifying_orders else None
    avg_value = round(total_spent / total_orders, 2) if total_orders > 0 else Decimal("0.00")

    summary = CustomerPurchaseSummary(
        total_orders=total_orders,
        total_spent=round(total_spent, 2),
        last_order_date=last_order_date,
        average_order_value=avg_value,
    )

    return ApiResponse.ok(
        CustomerOrdersResponse(
            customer_id=customer_id,
            summary=summary,
            orders=[OrderResponse.model_validate(o) for o in orders],
        )
    )

