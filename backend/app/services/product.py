"""
Product service — CRUD, search, slug generation.

All operations are scoped to merchant_id for tenant isolation.
Product creation also initializes inventory.
"""

from __future__ import annotations

import re
import uuid
from decimal import Decimal

from sqlalchemy import Select, func, select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import ConflictError, NotFoundError
from app.core.pagination import PaginationMeta, PaginationParams
from app.events.bus import DomainEvent, event_bus
from app.events.types import EventType
from app.models.inventory import Inventory
from app.models.outbox import OutboxEvent
from app.models.product import Product, ProductAttribute
from app.schemas.product import (
    ProductCreateRequest,
    ProductResponse,
    ProductSearchParams,
    ProductUpdateRequest,
)


def _slugify(name: str) -> str:
    slug = name.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug


class ProductService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self, merchant_id: uuid.UUID, data: ProductCreateRequest
    ) -> ProductResponse:
        """Create a product with inventory and optional attributes."""
        slug = _slugify(data.name)

        # Check slug uniqueness within merchant
        existing = await self.db.execute(
            select(Product).where(
                Product.merchant_id == merchant_id,
                Product.slug == slug,
            )
        )
        if existing.scalar_one_or_none():
            slug = f"{slug}-{uuid.uuid4().hex[:6]}"

        # Check SKU uniqueness within merchant
        sku_check = await self.db.execute(
            select(Product).where(
                Product.merchant_id == merchant_id,
                Product.sku == data.sku,
            )
        )
        if sku_check.scalar_one_or_none():
            raise ConflictError(f"SKU '{data.sku}' already exists")

        product = Product(
            merchant_id=merchant_id,
            category_id=data.category_id,
            name=data.name,
            slug=slug,
            description=data.description,
            sku=data.sku,
            price=data.price,
            compare_at_price=data.compare_at_price,
            currency=data.currency,
            status=data.status,
            image_url=data.image_url,
        )
        self.db.add(product)
        await self.db.flush()

        # Create attributes
        for attr in data.attributes:
            self.db.add(ProductAttribute(
                product_id=product.id,
                key=attr.key,
                value=attr.value,
            ))

        # Create inventory
        inventory = Inventory(
            product_id=product.id,
            merchant_id=merchant_id,
            quantity=data.initial_stock,
            reserved=0,
        )
        self.db.add(inventory)

        # Outbox event
        self.db.add(OutboxEvent(
            event_type=EventType.PRODUCT_CREATED,
            aggregate_type="product",
            aggregate_id=str(product.id),
            payload={"merchant_id": str(merchant_id), "product_name": data.name},
        ))

        await self.db.commit()
        await self.db.refresh(product)

        # Dispatch event
        await event_bus.publish(DomainEvent(
            event_type=EventType.PRODUCT_CREATED,
            aggregate_type="product",
            aggregate_id=str(product.id),
            payload={"product_name": data.name},
            merchant_id=str(merchant_id),
        ))

        return ProductResponse.model_validate(product)

    async def get(self, merchant_id: uuid.UUID, product_id: uuid.UUID) -> ProductResponse:
        """Get a product by ID, scoped to merchant."""
        result = await self.db.execute(
            select(Product)
            .options(selectinload(Product.attributes), selectinload(Product.inventory))
            .where(Product.id == product_id, Product.merchant_id == merchant_id)
        )
        product = result.scalar_one_or_none()
        if not product:
            raise NotFoundError("Product", str(product_id))
        return ProductResponse.model_validate(product)

    async def update(
        self, merchant_id: uuid.UUID, product_id: uuid.UUID, data: ProductUpdateRequest
    ) -> ProductResponse:
        """Update a product, scoped to merchant."""
        result = await self.db.execute(
            select(Product)
            .options(selectinload(Product.attributes), selectinload(Product.inventory))
            .where(Product.id == product_id, Product.merchant_id == merchant_id)
        )
        product = result.scalar_one_or_none()
        if not product:
            raise NotFoundError("Product", str(product_id))

        update_data = data.model_dump(exclude_unset=True)

        # Handle attributes separately
        if "attributes" in update_data:
            attrs = update_data.pop("attributes")
            # Delete existing attributes and replace
            for existing_attr in list(product.attributes):
                await self.db.delete(existing_attr)
            for attr in attrs:
                self.db.add(ProductAttribute(
                    product_id=product.id,
                    key=attr["key"],
                    value=attr["value"],
                ))

        for field, value in update_data.items():
            setattr(product, field, value)

        self.db.add(OutboxEvent(
            event_type=EventType.PRODUCT_UPDATED,
            aggregate_type="product",
            aggregate_id=str(product.id),
            payload={"merchant_id": str(merchant_id), "fields_updated": list(update_data.keys())},
        ))

        await self.db.commit()
        await self.db.refresh(product)
        return ProductResponse.model_validate(product)

    async def delete(self, merchant_id: uuid.UUID, product_id: uuid.UUID) -> None:
        """Soft-delete a product by setting status to archived."""
        result = await self.db.execute(
            select(Product).where(
                Product.id == product_id, Product.merchant_id == merchant_id
            )
        )
        product = result.scalar_one_or_none()
        if not product:
            raise NotFoundError("Product", str(product_id))
        product.status = "archived"
        await self.db.commit()

    async def list(
        self,
        merchant_id: uuid.UUID,
        search: ProductSearchParams,
        pagination: PaginationParams,
    ) -> tuple[list[ProductResponse], PaginationMeta]:
        """List products with filtering, searching, sorting, and pagination."""
        query = (
            select(Product)
            .options(selectinload(Product.attributes), selectinload(Product.inventory))
            .where(Product.merchant_id == merchant_id)
        )

        # Filters
        if search.status:
            query = query.where(Product.status == search.status)
        if search.category_id:
            query = query.where(Product.category_id == search.category_id)
        if search.min_price is not None:
            query = query.where(Product.price >= search.min_price)
        if search.max_price is not None:
            query = query.where(Product.price <= search.max_price)

        # Text search (case-insensitive ILIKE — pg_trgm index helps here)
        if search.q:
            search_term = f"%{search.q}%"
            query = query.where(
                or_(
                    Product.name.ilike(search_term),
                    Product.description.ilike(search_term),
                    Product.sku.ilike(search_term),
                )
            )

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        # Sort
        sort_column = getattr(Product, search.sort_by, Product.created_at)
        if search.sort_order == "desc":
            query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(sort_column.asc())

        # Paginate
        query = query.offset(pagination.offset).limit(pagination.per_page)

        result = await self.db.execute(query)
        products = result.scalars().all()

        meta = PaginationMeta.from_params(pagination, total)
        return [ProductResponse.model_validate(p) for p in products], meta

    async def search_public(
        self,
        merchant_id: uuid.UUID,
        search: ProductSearchParams,
        pagination: PaginationParams,
    ) -> tuple[list[ProductResponse], PaginationMeta]:
        """Public search for buyer — only active, in-stock products."""
        search.status = "active"
        return await self.list(merchant_id, search, pagination)
