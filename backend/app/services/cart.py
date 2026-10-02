"""
Cart service — cart lifecycle management.

Lifecycle: active → checkout → converted | abandoned | expired
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundError, ValidationError
from app.models.cart import Cart, CartItem
from app.models.product import Product
from app.models.inventory import Inventory
from app.schemas.cart import CartCreateRequest, CartItemAddRequest, CartItemUpdateRequest, CartResponse, CartItemResponse


class CartService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, merchant_id: uuid.UUID, data: CartCreateRequest) -> CartResponse:
        """Create a new cart."""
        cart = Cart(
            merchant_id=merchant_id,
            customer_id=data.customer_id,
            status="active",
        )
        self.db.add(cart)
        await self.db.commit()
        await self.db.refresh(cart)
        return await self._to_response(cart)

    async def get(self, merchant_id: uuid.UUID, cart_id: uuid.UUID) -> CartResponse:
        """Get a cart with items."""
        cart = await self._get_cart(merchant_id, cart_id)
        return await self._to_response(cart)

    async def add_item(
        self, merchant_id: uuid.UUID, cart_id: uuid.UUID, data: CartItemAddRequest
    ) -> CartResponse:
        """Add a product to the cart."""
        cart = await self._get_cart(merchant_id, cart_id)
        if cart.status != "active":
            raise ValidationError(f"Cannot modify cart in '{cart.status}' status")

        # Verify product exists and belongs to merchant
        product = await self._get_product(merchant_id, data.product_id)

        # Check stock availability
        inv_result = await self.db.execute(
            select(Inventory).where(
                Inventory.product_id == data.product_id,
                Inventory.merchant_id == merchant_id,
            )
        )
        inventory = inv_result.scalar_one_or_none()
        if not inventory or inventory.available < data.quantity:
            avail = inventory.available if inventory else 0
            raise ValidationError(
                f"Insufficient stock: {avail} available, {data.quantity} requested"
            )

        # Check if item already in cart — update quantity if so
        existing_item = None
        for item in cart.items:
            if item.product_id == data.product_id:
                existing_item = item
                break

        if existing_item:
            existing_item.quantity += data.quantity
        else:
            cart_item = CartItem(
                cart_id=cart.id,
                product_id=data.product_id,
                quantity=data.quantity,
                unit_price=product.price,
            )
            self.db.add(cart_item)

        await self.db.commit()
        await self.db.refresh(cart)
        return await self._to_response(cart)

    async def update_item(
        self,
        merchant_id: uuid.UUID,
        cart_id: uuid.UUID,
        item_id: uuid.UUID,
        data: CartItemUpdateRequest,
    ) -> CartResponse:
        """Update cart item quantity."""
        cart = await self._get_cart(merchant_id, cart_id)
        if cart.status != "active":
            raise ValidationError(f"Cannot modify cart in '{cart.status}' status")

        item = None
        for ci in cart.items:
            if ci.id == item_id:
                item = ci
                break
        if not item:
            raise NotFoundError("CartItem", str(item_id))

        item.quantity = data.quantity
        await self.db.commit()
        await self.db.refresh(cart)
        return await self._to_response(cart)

    async def remove_item(
        self, merchant_id: uuid.UUID, cart_id: uuid.UUID, item_id: uuid.UUID
    ) -> CartResponse:
        """Remove an item from the cart."""
        cart = await self._get_cart(merchant_id, cart_id)
        if cart.status != "active":
            raise ValidationError(f"Cannot modify cart in '{cart.status}' status")

        item = None
        for ci in cart.items:
            if ci.id == item_id:
                item = ci
                break
        if not item:
            raise NotFoundError("CartItem", str(item_id))

        await self.db.delete(item)
        await self.db.commit()
        await self.db.refresh(cart)
        return await self._to_response(cart)

    async def _get_cart(self, merchant_id: uuid.UUID, cart_id: uuid.UUID) -> Cart:
        result = await self.db.execute(
            select(Cart)
            .options(selectinload(Cart.items))
            .where(Cart.id == cart_id, Cart.merchant_id == merchant_id)
        )
        cart = result.scalar_one_or_none()
        if not cart:
            raise NotFoundError("Cart", str(cart_id))
        return cart

    async def _get_product(self, merchant_id: uuid.UUID, product_id: uuid.UUID) -> Product:
        result = await self.db.execute(
            select(Product).where(
                Product.id == product_id,
                Product.merchant_id == merchant_id,
                Product.status == "active",
            )
        )
        product = result.scalar_one_or_none()
        if not product:
            raise NotFoundError("Product", str(product_id))
        return product

    async def _to_response(self, cart: Cart) -> CartResponse:
        items = []
        for item in cart.items:
            # Eagerly load product name
            prod_result = await self.db.execute(
                select(Product.name).where(Product.id == item.product_id)
            )
            product_name = prod_result.scalar()
            items.append(CartItemResponse(
                id=item.id,
                product_id=item.product_id,
                product_name=product_name,
                quantity=item.quantity,
                unit_price=item.unit_price,
                line_total=item.line_total,
            ))
        return CartResponse(
            id=cart.id,
            merchant_id=cart.merchant_id,
            customer_id=cart.customer_id,
            status=cart.status,
            items=items,
            subtotal=cart.subtotal,
            item_count=cart.item_count,
            created_at=cart.created_at,
        )
