"""
Flowmint AI — Safe Read-Only Buyer Tools (Phase 2A).

Provides authoritative product and inventory data to the Buyer Agent.
Strictly read-only; queries are always scoped to context.merchant_id.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from app.ai.tools.base import BaseTool, RiskLevel, ToolContext, ToolResult
from app.models.category import Category
from app.models.inventory import Inventory
from app.models.product import Product, ProductAttribute


# ============================================================
# 1. Search Products Tool
# ============================================================

class SearchProductsParams(BaseModel):
    query: str = Field(default="", description="Search keywords for product name, description, or SKU")
    category_id: str | None = Field(default=None, description="Filter by category UUID")
    min_price: float | None = Field(default=None, description="Minimum price filter in INR")
    max_price: float | None = Field(default=None, description="Maximum price filter in INR")
    in_stock_only: bool = Field(default=False, description="Filter for products with available stock > 0")
    limit: int = Field(default=10, ge=1, le=50, description="Maximum number of items to return")


class SearchProductsTool(BaseTool):
    @property
    def name(self) -> str:
        return "search_products"

    @property
    def description(self) -> str:
        return (
            "Search for products in the merchant catalog by keyword, price range, and category. "
            "Returns authoritative product details and real-time stock levels."
        )

    @property
    def parameters_schema(self) -> type[BaseModel]:
        return SearchProductsParams

    async def execute(self, params: SearchProductsParams, context: ToolContext) -> ToolResult:
        query = (
            select(Product)
            .options(
                selectinload(Product.inventory),
                selectinload(Product.category),
                selectinload(Product.attributes),
            )
            .where(
                Product.merchant_id == context.merchant_id,
                Product.status == "active",
            )
        )

        if params.query.strip():
            words = [w for w in params.query.strip().split() if len(w) > 1]
            if words:
                word_clauses = [
                    or_(
                        Product.name.ilike(f"%{w}%"),
                        Product.description.ilike(f"%{w}%"),
                        Product.sku.ilike(f"%{w}%"),
                    )
                    for w in words
                ]
                query = query.where(or_(*word_clauses))

        if params.category_id:
            try:
                cat_uuid = uuid.UUID(params.category_id)
                query = query.where(Product.category_id == cat_uuid)
            except ValueError:
                pass

        if params.min_price is not None:
            query = query.where(Product.price >= Decimal(str(params.min_price)))

        if params.max_price is not None:
            query = query.where(Product.price <= Decimal(str(params.max_price)))

        query = query.order_by(Product.name.asc()).limit(params.limit)

        result = await context.db.execute(query)
        products = result.scalars().all()

        output = []
        for p in products:
            inv = p.inventory
            available_stock = inv.available if inv else 0
            if params.in_stock_only and available_stock <= 0:
                continue

            output.append({
                "id": str(p.id),
                "name": p.name,
                "sku": p.sku,
                "slug": p.slug,
                "price": str(p.price),
                "compare_at_price": str(p.compare_at_price) if p.compare_at_price else None,
                "currency": p.currency,
                "category": p.category.name if p.category else None,
                "available_stock": available_stock,
                "in_stock": available_stock > 0,
                "attributes": {a.key: a.value for a in p.attributes},
            })

        return ToolResult.ok(data=output, message=f"Found {len(output)} product(s)")


# ============================================================
# 2. Get Product Tool
# ============================================================

class GetProductParams(BaseModel):
    product_id: str | None = Field(default=None, description="UUID of the product")
    sku: str | None = Field(default=None, description="Exact SKU of the product")
    slug: str | None = Field(default=None, description="URL slug of the product")


class GetProductTool(BaseTool):
    @property
    def name(self) -> str:
        return "get_product"

    @property
    def description(self) -> str:
        return (
            "Retrieve complete details for a single product by its ID, SKU, or slug, "
            "including pricing, attributes, description, and exact live inventory."
        )

    @property
    def parameters_schema(self) -> type[BaseModel]:
        return GetProductParams

    async def execute(self, params: GetProductParams, context: ToolContext) -> ToolResult:
        query = (
            select(Product)
            .options(
                selectinload(Product.inventory),
                selectinload(Product.category),
                selectinload(Product.attributes),
            )
            .where(Product.merchant_id == context.merchant_id)
        )

        if params.product_id:
            try:
                p_uuid = uuid.UUID(params.product_id)
                query = query.where(Product.id == p_uuid)
            except ValueError:
                return ToolResult.fail("Invalid product_id UUID format")
        elif params.sku:
            query = query.where(Product.sku == params.sku.strip())
        elif params.slug:
            query = query.where(Product.slug == params.slug.strip())
        else:
            return ToolResult.fail("Must provide at least one of product_id, sku, or slug")

        res = await context.db.execute(query)
        product = res.scalar_one_or_none()
        if not product:
            return ToolResult.fail("Product not found in this store")

        inv = product.inventory
        available = inv.available if inv else 0

        data = {
            "id": str(product.id),
            "name": product.name,
            "sku": product.sku,
            "slug": product.slug,
            "description": product.description,
            "price": str(product.price),
            "compare_at_price": str(product.compare_at_price) if product.compare_at_price else None,
            "currency": product.currency,
            "status": product.status,
            "category": product.category.name if product.category else None,
            "inventory": {
                "quantity": inv.quantity if inv else 0,
                "reserved": inv.reserved if inv else 0,
                "available": available,
                "is_low_stock": inv.is_low_stock if inv else False,
            },
            "attributes": {a.key: a.value for a in product.attributes},
        }
        return ToolResult.ok(data=data)


# ============================================================
# 3. Compare Products Tool
# ============================================================

class CompareProductsParams(BaseModel):
    product_ids: list[str] = Field(description="List of product UUIDs to compare side-by-side (2 to 5)")


class CompareProductsTool(BaseTool):
    @property
    def name(self) -> str:
        return "compare_products"

    @property
    def description(self) -> str:
        return "Compare 2 to 5 products side-by-side on price, stock, specs, and attributes."

    @property
    def parameters_schema(self) -> type[BaseModel]:
        return CompareProductsParams

    async def execute(self, params: CompareProductsParams, context: ToolContext) -> ToolResult:
        if len(params.product_ids) < 2:
            return ToolResult.fail("At least 2 product IDs are required for comparison")
        if len(params.product_ids) > 5:
            return ToolResult.fail("Cannot compare more than 5 products at once")

        uuids = []
        for pid in params.product_ids:
            try:
                uuids.append(uuid.UUID(pid))
            except ValueError:
                return ToolResult.fail(f"Invalid UUID: {pid}")

        query = (
            select(Product)
            .options(
                selectinload(Product.inventory),
                selectinload(Product.category),
                selectinload(Product.attributes),
            )
            .where(
                Product.merchant_id == context.merchant_id,
                Product.id.in_(uuids),
            )
        )
        res = await context.db.execute(query)
        products = res.scalars().all()

        comparison = []
        for p in products:
            inv = p.inventory
            comparison.append({
                "id": str(p.id),
                "name": p.name,
                "sku": p.sku,
                "price": str(p.price),
                "available_stock": inv.available if inv else 0,
                "category": p.category.name if p.category else None,
                "attributes": {a.key: a.value for a in p.attributes},
            })

        return ToolResult.ok(data=comparison, message=f"Compared {len(comparison)} products")


# ============================================================
# 4. Check Inventory Tool
# ============================================================

class CheckInventoryParams(BaseModel):
    product_id: str = Field(description="UUID of the product to check inventory for")


class CheckInventoryTool(BaseTool):
    @property
    def name(self) -> str:
        return "check_inventory"

    @property
    def description(self) -> str:
        return "Check exact live inventory availability, reserved units, and low-stock status for a product."

    @property
    def parameters_schema(self) -> type[BaseModel]:
        return CheckInventoryParams

    async def execute(self, params: CheckInventoryParams, context: ToolContext) -> ToolResult:
        try:
            p_uuid = uuid.UUID(params.product_id)
        except ValueError:
            return ToolResult.fail("Invalid product_id UUID")

        query = select(Inventory).where(
            Inventory.merchant_id == context.merchant_id,
            Inventory.product_id == p_uuid,
        )
        res = await context.db.execute(query)
        inv = res.scalar_one_or_none()
        if not inv:
            return ToolResult.fail(f"Inventory record for product {params.product_id} not found")

        return ToolResult.ok(data={
            "product_id": str(inv.product_id),
            "quantity": inv.quantity,
            "reserved": inv.reserved,
            "available": inv.available,
            "low_stock_threshold": inv.low_stock_threshold,
            "is_in_stock": inv.is_in_stock,
            "is_low_stock": inv.is_low_stock,
        })


# ============================================================
# 5. Get Related Products Tool
# ============================================================

class GetRelatedProductsParams(BaseModel):
    product_id: str = Field(description="UUID of the source product")
    limit: int = Field(default=4, ge=1, le=10, description="Max related products to return")


class GetRelatedProductsTool(BaseTool):
    @property
    def name(self) -> str:
        return "get_related_products"

    @property
    def description(self) -> str:
        return "Find related or alternative products in the same category or with matching attributes."

    @property
    def parameters_schema(self) -> type[BaseModel]:
        return GetRelatedProductsParams

    async def execute(self, params: GetRelatedProductsParams, context: ToolContext) -> ToolResult:
        try:
            p_uuid = uuid.UUID(params.product_id)
        except ValueError:
            return ToolResult.fail("Invalid product_id UUID")

        # Get target product's category
        src_res = await context.db.execute(
            select(Product).where(
                Product.id == p_uuid,
                Product.merchant_id == context.merchant_id,
            )
        )
        src = src_res.scalar_one_or_none()
        if not src:
            return ToolResult.fail("Source product not found")

        query = (
            select(Product)
            .options(selectinload(Product.inventory))
            .where(
                Product.merchant_id == context.merchant_id,
                Product.id != p_uuid,
                Product.status == "active",
            )
        )
        if src.category_id:
            query = query.where(Product.category_id == src.category_id)

        query = query.limit(params.limit)
        res = await context.db.execute(query)
        items = res.scalars().all()

        output = [
            {
                "id": str(item.id),
                "name": item.name,
                "price": str(item.price),
                "available_stock": item.inventory.available if item.inventory else 0,
            }
            for item in items
        ]
        return ToolResult.ok(data=output, message=f"Found {len(output)} related product(s)")
