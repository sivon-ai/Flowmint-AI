"""
Tests for authentication, product CRUD, inventory, cart, order, payment, and tenant isolation.
"""

import hashlib
import hmac
import json
import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient

from app.models.cart import Cart, CartItem
from app.models.customer import Customer
from app.models.inventory import Inventory
from app.models.merchant import Merchant
from app.models.order import Order
from app.models.payment import Payment, PaymentEvent
from app.models.product import Product
from app.models.user import User


# ============================================================
# AUTH TESTS
# ============================================================

class TestAuth:
    @pytest.mark.asyncio
    async def test_register(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/register", json={
            "merchant_name": "New Store",
            "email": "new@store.com",
            "password": "securepass123",
            "full_name": "Store Owner",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["success"] is True
        assert "access_token" in data["data"]
        assert "refresh_token" in data["data"]

    @pytest.mark.asyncio
    async def test_register_duplicate_email(self, client: AsyncClient, merchant: Merchant):
        resp = await client.post("/api/v1/auth/register", json={
            "merchant_name": "Dup Store",
            "email": merchant.email,
            "password": "securepass123",
            "full_name": "Owner",
        })
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_login(self, client: AsyncClient, user: User):
        resp = await client.post("/api/v1/auth/login", json={
            "email": user.email,
            "password": "testpass123",
        })
        assert resp.status_code == 200
        assert resp.json()["data"]["access_token"]

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, client: AsyncClient, user: User):
        resp = await client.post("/api/v1/auth/login", json={
            "email": user.email,
            "password": "wrongpassword",
        })
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_get_me(self, client: AsyncClient, auth_headers: dict, user: User):
        resp = await client.get("/api/v1/auth/me", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["data"]["email"] == user.email

    @pytest.mark.asyncio
    async def test_unauthorized_without_token(self, client: AsyncClient):
        resp = await client.get("/api/v1/auth/me")
        assert resp.status_code == 403  # HTTPBearer returns 403 when no creds


# ============================================================
# PRODUCT TESTS
# ============================================================

class TestProducts:
    @pytest.mark.asyncio
    async def test_create_product(self, client: AsyncClient, auth_headers: dict):
        resp = await client.post("/api/v1/products", headers=auth_headers, json={
            "name": "Gaming Mouse",
            "sku": "MOUSE-001",
            "price": 2999.00,
            "description": "High DPI gaming mouse",
            "initial_stock": 100,
            "attributes": [
                {"key": "DPI", "value": "16000"},
                {"key": "Buttons", "value": "7"},
            ],
        })
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["name"] == "Gaming Mouse"
        assert data["sku"] == "MOUSE-001"
        assert data["inventory"]["quantity"] == 100
        assert len(data["attributes"]) == 2

    @pytest.mark.asyncio
    async def test_create_duplicate_sku(
        self, client: AsyncClient, auth_headers: dict, product: Product
    ):
        resp = await client.post("/api/v1/products", headers=auth_headers, json={
            "name": "Another Product",
            "sku": product.sku,  # duplicate
            "price": 1000.00,
        })
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_get_product(
        self, client: AsyncClient, auth_headers: dict, product: Product
    ):
        resp = await client.get(
            f"/api/v1/products/{product.id}", headers=auth_headers
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["id"] == str(product.id)

    @pytest.mark.asyncio
    async def test_list_products(
        self, client: AsyncClient, auth_headers: dict, product: Product
    ):
        resp = await client.get("/api/v1/products", headers=auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()["data"]) >= 1
        assert resp.json()["meta"]["total"] >= 1

    @pytest.mark.asyncio
    async def test_search_products(
        self, client: AsyncClient, auth_headers: dict, product: Product
    ):
        resp = await client.get(
            "/api/v1/products?q=laptop", headers=auth_headers
        )
        assert resp.status_code == 200
        assert len(resp.json()["data"]) >= 1

    @pytest.mark.asyncio
    async def test_update_product(
        self, client: AsyncClient, auth_headers: dict, product: Product
    ):
        resp = await client.patch(
            f"/api/v1/products/{product.id}",
            headers=auth_headers,
            json={"price": 54999.00},
        )
        assert resp.status_code == 200
        assert float(resp.json()["data"]["price"]) == 54999.00

    @pytest.mark.asyncio
    async def test_delete_product(
        self, client: AsyncClient, auth_headers: dict, product: Product
    ):
        resp = await client.delete(
            f"/api/v1/products/{product.id}", headers=auth_headers
        )
        assert resp.status_code == 204


# ============================================================
# TENANT ISOLATION TESTS
# ============================================================

class TestTenantIsolation:
    @pytest.mark.asyncio
    async def test_cannot_access_other_merchant_product(
        self,
        client: AsyncClient,
        auth_headers_b: dict,
        product: Product,
    ):
        """Merchant B should NOT be able to access Merchant A's product."""
        resp = await client.get(
            f"/api/v1/products/{product.id}", headers=auth_headers_b
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_cannot_list_other_merchant_products(
        self,
        client: AsyncClient,
        auth_headers_b: dict,
        product: Product,
    ):
        """Merchant B should see 0 products (not Merchant A's)."""
        resp = await client.get("/api/v1/products", headers=auth_headers_b)
        assert resp.status_code == 200
        assert len(resp.json()["data"]) == 0


# ============================================================
# INVENTORY TESTS
# ============================================================

class TestInventory:
    @pytest.mark.asyncio
    async def test_get_inventory(
        self, client: AsyncClient, auth_headers: dict, product: Product
    ):
        resp = await client.get(
            f"/api/v1/inventory/{product.id}", headers=auth_headers
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["quantity"] == 50

    @pytest.mark.asyncio
    async def test_update_inventory(
        self, client: AsyncClient, auth_headers: dict, product: Product
    ):
        resp = await client.patch(
            f"/api/v1/inventory/{product.id}",
            headers=auth_headers,
            json={"quantity": 200},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["quantity"] == 200


# ============================================================
# CART TESTS
# ============================================================

class TestCart:
    @pytest.mark.asyncio
    async def test_cart_lifecycle(
        self,
        client: AsyncClient,
        auth_headers: dict,
        product: Product,
        customer: Customer,
    ):
        # Create cart
        resp = await client.post("/api/v1/carts", headers=auth_headers, json={
            "customer_id": str(customer.id),
        })
        assert resp.status_code == 201
        cart_id = resp.json()["data"]["id"]

        # Add item
        resp = await client.post(
            f"/api/v1/carts/{cart_id}/items",
            headers=auth_headers,
            json={"product_id": str(product.id), "quantity": 2},
        )
        assert resp.status_code == 200
        assert len(resp.json()["data"]["items"]) == 1
        assert resp.json()["data"]["item_count"] == 2
        item_id = resp.json()["data"]["items"][0]["id"]

        # Update quantity
        resp = await client.patch(
            f"/api/v1/carts/{cart_id}/items/{item_id}",
            headers=auth_headers,
            json={"quantity": 3},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["items"][0]["quantity"] == 3

        # Remove item
        resp = await client.delete(
            f"/api/v1/carts/{cart_id}/items/{item_id}",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert len(resp.json()["data"]["items"]) == 0


# ============================================================
# ORDER TESTS
# ============================================================

class TestOrders:
    @pytest.mark.asyncio
    async def test_create_order_from_cart(
        self,
        client: AsyncClient,
        auth_headers: dict,
        product: Product,
        customer: Customer,
    ):
        # Create cart with items
        resp = await client.post("/api/v1/carts", headers=auth_headers, json={
            "customer_id": str(customer.id),
        })
        cart_id = resp.json()["data"]["id"]

        await client.post(
            f"/api/v1/carts/{cart_id}/items",
            headers=auth_headers,
            json={"product_id": str(product.id), "quantity": 2},
        )

        # Create order
        resp = await client.post("/api/v1/orders", headers=auth_headers, json={
            "cart_id": cart_id,
            "shipping_address": {"line1": "123 Test St", "city": "Mumbai"},
        })
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["status"] == "pending"
        assert data["order_number"].startswith("FM-")
        assert len(data["items"]) == 1
        assert float(data["total"]) == 119998.00  # 59999 * 2

    @pytest.mark.asyncio
    async def test_create_order_empty_cart(
        self,
        client: AsyncClient,
        auth_headers: dict,
        customer: Customer,
    ):
        # Create empty cart
        resp = await client.post("/api/v1/carts", headers=auth_headers, json={
            "customer_id": str(customer.id),
        })
        cart_id = resp.json()["data"]["id"]

        resp = await client.post("/api/v1/orders", headers=auth_headers, json={
            "cart_id": cart_id,
        })
        assert resp.status_code == 422  # Cart is empty


# ============================================================
# PAYMENT STATE MACHINE TESTS
# ============================================================

class TestPaymentStateMachine:
    @pytest.mark.asyncio
    async def test_payment_transitions(self, db_session):
        """Test that only valid payment state transitions are allowed."""
        from app.models.payment import PAYMENT_TRANSITIONS

        # pending → authorized ✓
        assert "authorized" in PAYMENT_TRANSITIONS["pending"]
        # pending → failed ✓
        assert "failed" in PAYMENT_TRANSITIONS["pending"]
        # pending → captured ✓ (direct / auto-capture)
        assert "captured" in PAYMENT_TRANSITIONS["pending"]
        # authorized → captured ✓
        assert "captured" in PAYMENT_TRANSITIONS["authorized"]
        # captured → refunded ✓
        assert "refunded" in PAYMENT_TRANSITIONS["captured"]
        # failed → anything ✗
        assert len(PAYMENT_TRANSITIONS["failed"]) == 0
        # refunded → anything ✗
        assert len(PAYMENT_TRANSITIONS["refunded"]) == 0


# ============================================================
# WEBHOOK TESTS
# ============================================================

class TestWebhookSecurity:
    @pytest.mark.asyncio
    async def test_webhook_rejects_invalid_signature(self, client: AsyncClient):
        """Webhook must reject requests with invalid Razorpay signatures."""
        payload = json.dumps({"event": "payment.captured"}).encode()
        resp = await client.post(
            "/api/v1/payments/webhook",
            content=payload,
            headers={
                "X-Razorpay-Signature": "invalid_signature",
                "Content-Type": "application/json",
            },
        )
        assert resp.status_code == 400  # PaymentError

    @pytest.mark.asyncio
    async def test_webhook_does_not_require_jwt(self, client: AsyncClient):
        """Webhook endpoint should be accessible without JWT auth."""
        # Just verify it doesn't return 401/403 for missing JWT
        # It will fail on signature validation, which is correct
        payload = json.dumps({"event": "test"}).encode()
        resp = await client.post(
            "/api/v1/payments/webhook",
            content=payload,
            headers={
                "X-Razorpay-Signature": "test",
                "Content-Type": "application/json",
            },
        )
        # Should be 400 (bad signature), NOT 401/403 (auth required)
        assert resp.status_code == 400


# ============================================================
# OUTBOX EVENT TESTS
# ============================================================

class TestOutboxEvents:
    @pytest.mark.asyncio
    async def test_product_creation_creates_outbox_event(
        self, client: AsyncClient, auth_headers: dict, db_session
    ):
        """Creating a product should also create an outbox event."""
        from sqlalchemy import select
        from app.models.outbox import OutboxEvent

        resp = await client.post("/api/v1/products", headers=auth_headers, json={
            "name": "Outbox Test Product",
            "sku": "OUTBOX-001",
            "price": 999.00,
        })
        assert resp.status_code == 201

        # Check outbox
        result = await db_session.execute(
            select(OutboxEvent).where(OutboxEvent.event_type == "product.created")
        )
        events = result.scalars().all()
        assert len(events) >= 1


# ============================================================
# HEALTH CHECK
# ============================================================

class TestHealth:
    @pytest.mark.asyncio
    async def test_health(self, client: AsyncClient):
        resp = await client.get("/api/v1/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
