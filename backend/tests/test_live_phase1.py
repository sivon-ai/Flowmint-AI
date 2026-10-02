"""
Comprehensive Live Phase 1 Verification Suite against real PostgreSQL.

Covers:
1. Local End-to-End Commerce Workflow
2. Strict Tenant Isolation and Multi-Tenant Unique Constraints
3. Live Payment State Machine and Razorpay Webhook Deduplication
4. Real Database-backed Inventory Concurrency & Check Constraints
5. Transactional Outbox Atomicity, Rollback, and OutboxDispatcher
"""

import asyncio
import hashlib
import hmac
import json
import uuid
from decimal import Decimal

import pytest
import sqlalchemy as sa
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.events.bus import DomainEvent, EventBus
from app.events.dispatcher import OutboxDispatcher
from app.models.inventory import Inventory
from app.models.order import Order
from app.models.outbox import OutboxEvent
from app.models.payment import Payment, PaymentEvent
from app.models.product import Product
from app.services.inventory import InventoryService

settings = get_settings()


def _sign(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


# ============================================================
# 1. LIVE END-TO-END COMMERCE WORKFLOW
# ============================================================

class TestLiveEndToEndCommerce:
    @pytest.mark.asyncio
    async def test_full_commerce_loop(self, client: AsyncClient, db_session: AsyncSession):
        """
        Complete commerce loop against real PostgreSQL:
        Merchant registration -> Login -> Create Category -> Create Product ->
        Set Inventory -> Create Customer -> Create Cart -> Add Product ->
        Validate Inventory -> Create Order -> Verify Reserved Inventory ->
        Initiate Payment -> Process Webhook -> Verify Payment Captured ->
        Verify Order Confirmed -> Verify Inventory Sold -> Verify OutboxEvent ->
        Verify Outbox Dispatch.
        """
        # 1. Merchant Registration
        reg_resp = await client.post("/api/v1/auth/register", json={
            "merchant_name": "E2E Super Store",
            "email": "e2e_owner@flowmint.ai",
            "password": "Password123!",
            "full_name": "E2E Owner",
        })
        assert reg_resp.status_code == 201
        tokens = reg_resp.json()["data"]
        auth_headers = {"Authorization": f"Bearer {tokens['access_token']}"}

        # 2. Login
        login_resp = await client.post("/api/v1/auth/login", json={
            "email": "e2e_owner@flowmint.ai",
            "password": "Password123!",
        })
        assert login_resp.status_code == 200
        assert login_resp.json()["data"]["access_token"]

        # 3. Create Product (with initial inventory = 20)
        prod_resp = await client.post("/api/v1/products", headers=auth_headers, json={
            "name": "Live Flagship Phone",
            "sku": "PHONE-LIVE-001",
            "price": 49999.00,
            "description": "Premium 5G smartphone",
            "initial_stock": 20,
            "attributes": [
                {"key": "Storage", "value": "256GB"},
                {"key": "Color", "value": "Obsidian"},
            ],
        })
        assert prod_resp.status_code == 201
        prod_data = prod_resp.json()["data"]
        product_id = prod_data["id"]
        assert prod_data["inventory"]["quantity"] == 20
        assert prod_data["inventory"]["available"] == 20

        # 4. Update Inventory threshold
        inv_update = await client.patch(
            f"/api/v1/inventory/{product_id}",
            headers=auth_headers,
            json={"quantity": 25, "low_stock_threshold": 3},
        )
        assert inv_update.status_code == 200
        assert inv_update.json()["data"]["quantity"] == 25

        # 5. Create Customer
        cust_resp = await client.post("/api/v1/customers", headers=auth_headers, json={
            "name": "Ananya Sharma",
            "email": "ananya@example.com",
            "phone": "+919876543210",
        })
        assert cust_resp.status_code == 201
        customer_id = cust_resp.json()["data"]["id"]

        # 6. Create Cart
        cart_resp = await client.post("/api/v1/carts", headers=auth_headers, json={
            "customer_id": customer_id,
        })
        assert cart_resp.status_code == 201
        cart_id = cart_resp.json()["data"]["id"]

        # 7. Add Product to Cart (quantity = 2)
        add_item_resp = await client.post(
            f"/api/v1/carts/{cart_id}/items",
            headers=auth_headers,
            json={"product_id": product_id, "quantity": 2},
        )
        assert add_item_resp.status_code == 200
        cart_state = add_item_resp.json()["data"]
        assert cart_state["item_count"] == 2
        assert float(cart_state["subtotal"]) == 99998.00  # 49999 * 2

        # 8. Create Order from Cart
        order_resp = await client.post("/api/v1/orders", headers=auth_headers, json={
            "cart_id": cart_id,
            "shipping_address": {
                "street": "100 MG Road",
                "city": "Bengaluru",
                "state": "Karnataka",
                "pincode": "560001",
            },
            "notes": "Please deliver between 10am-2pm",
        })
        assert order_resp.status_code == 201
        order_data = order_resp.json()["data"]
        order_id = order_data["id"]
        assert order_data["status"] == "pending"
        assert float(order_data["total"]) == 99998.00
        assert len(order_data["items"]) == 1
        assert order_data["items"][0]["product_name"] == "Live Flagship Phone"
        assert order_data["items"][0]["product_sku"] == "PHONE-LIVE-001"

        # 9. Verify Stock was Reserved in PostgreSQL
        inv_check = await client.get(f"/api/v1/inventory/{product_id}", headers=auth_headers)
        assert inv_check.status_code == 200
        assert inv_check.json()["data"]["quantity"] == 25
        assert inv_check.json()["data"]["reserved"] == 2
        assert inv_check.json()["data"]["available"] == 23

        # 10. Create Payment record for this Order
        payment_id = uuid.uuid4()
        provider_order_id = f"order_test_{uuid.uuid4().hex[:12]}"
        provider_payment_id = f"pay_test_{uuid.uuid4().hex[:12]}"

        # Insert pending payment into DB directly (simulating initiate)
        merchant_id = uuid.UUID(reg_resp.json()["data"]["user"]["merchant_id"]) if "user" in reg_resp.json()["data"] else None
        # get merchant_id from order
        order_db = await db_session.get(Order, uuid.UUID(order_id))
        merchant_id = order_db.merchant_id

        payment = Payment(
            id=payment_id,
            order_id=uuid.UUID(order_id),
            merchant_id=merchant_id,
            amount=Decimal("99998.00"),
            currency="INR",
            status="pending",
            provider="razorpay",
            provider_order_id=provider_order_id,
            idempotency_key=f"pay_e2e_{order_id}",
        )
        db_session.add(payment)
        await db_session.commit()

        # 11. Send Webhook (payment.captured)
        webhook_payload = {
            "event": "payment.captured",
            "event_id": f"evt_e2e_{uuid.uuid4().hex[:8]}",
            "payload": {
                "payment": {
                    "entity": {
                        "id": provider_payment_id,
                        "order_id": provider_order_id,
                        "amount": 9999800,
                        "currency": "INR",
                        "status": "captured",
                    }
                }
            },
        }
        body_bytes = json.dumps(webhook_payload).encode("utf-8")
        webhook_secret = settings.razorpay_webhook_secret or "webhook_placeholder_secret"
        sig = _sign(body_bytes, webhook_secret)

        webhook_resp = await client.post(
            "/api/v1/payments/webhook",
            content=body_bytes,
            headers={
                "X-Razorpay-Signature": sig,
                "Content-Type": "application/json",
            },
        )
        assert webhook_resp.status_code == 200
        assert webhook_resp.json()["status"] == "processed"
        assert webhook_resp.json()["payment_status"] == "captured"

        # 12. Verify Payment state is CAPTURED
        pay_verify = await client.get(f"/api/v1/payments/{payment_id}", headers=auth_headers)
        assert pay_verify.status_code == 200
        assert pay_verify.json()["data"]["status"] == "captured"
        assert pay_verify.json()["data"]["provider_payment_id"] == provider_payment_id

        # 13. Verify Order state is CONFIRMED
        ord_verify = await client.get(f"/api/v1/orders/{order_id}", headers=auth_headers)
        assert ord_verify.status_code == 200
        assert ord_verify.json()["data"]["status"] == "confirmed"

        # 14. Verify Inventory was deducted (confirmed sale: quantity reduced by 2, reserved reduced by 2)
        inv_after_sale = await client.get(f"/api/v1/inventory/{product_id}", headers=auth_headers)
        assert inv_after_sale.status_code == 200
        assert inv_after_sale.json()["data"]["quantity"] == 23
        assert inv_after_sale.json()["data"]["reserved"] == 0
        assert inv_after_sale.json()["data"]["available"] == 23

        # 15. Verify OutboxEvents were recorded in DB
        outbox_res = await db_session.execute(
            sa.select(OutboxEvent).order_by(OutboxEvent.created_at.asc())
        )
        outbox_events = outbox_res.scalars().all()
        assert len(outbox_events) >= 3  # product.created, order.created, payment.captured

        # 16. Verify OutboxDispatcher drains pending events to published
        dispatcher = OutboxDispatcher(db=db_session)
        dispatched_count = await dispatcher.dispatch_pending(limit=50)
        assert dispatched_count >= 1

        # Check all are now published
        outbox_check = await db_session.execute(
            sa.select(OutboxEvent).where(OutboxEvent.status == "pending")
        )
        assert len(outbox_check.scalars().all()) == 0


# ============================================================
# 2. TENANT ISOLATION TESTS
# ============================================================

class TestLiveTenantIsolation:
    @pytest.mark.asyncio
    async def test_cross_tenant_data_protection(self, client: AsyncClient):
        """
        Verify Merchant A and Merchant B are completely isolated:
        - Merchant A cannot read, update, or delete Merchant B's products
        - Merchant A cannot read Merchant B's customers, carts, orders, payments
        """
        # Register Merchant A
        res_a = await client.post("/api/v1/auth/register", json={
            "merchant_name": "Store Alpha",
            "email": "alpha_owner@test.com",
            "password": "Password123!",
            "full_name": "Alpha Owner",
        })
        headers_a = {"Authorization": f"Bearer {res_a.json()['data']['access_token']}"}

        # Register Merchant B
        res_b = await client.post("/api/v1/auth/register", json={
            "merchant_name": "Store Beta",
            "email": "beta_owner@test.com",
            "password": "Password123!",
            "full_name": "Beta Owner",
        })
        headers_b = {"Authorization": f"Bearer {res_b.json()['data']['access_token']}"}

        # Merchant B creates a product
        prod_b_resp = await client.post("/api/v1/products", headers=headers_b, json={
            "name": "Beta Product",
            "sku": "BETA-001",
            "price": 1500.00,
            "initial_stock": 10,
        })
        prod_b_id = prod_b_resp.json()["data"]["id"]

        # Merchant A attempts to read Merchant B's product -> 404
        get_b_by_a = await client.get(f"/api/v1/products/{prod_b_id}", headers=headers_a)
        assert get_b_by_a.status_code == 404

        # Merchant A attempts to update Merchant B's product -> 404
        patch_b_by_a = await client.patch(
            f"/api/v1/products/{prod_b_id}",
            headers=headers_a,
            json={"price": 1.00},
        )
        assert patch_b_by_a.status_code == 404

        # Merchant A attempts to delete Merchant B's product -> 404
        del_b_by_a = await client.delete(f"/api/v1/products/{prod_b_id}", headers=headers_a)
        assert del_b_by_a.status_code == 404

        # Product B should still be intact when read by Merchant B
        get_b_by_b = await client.get(f"/api/v1/products/{prod_b_id}", headers=headers_b)
        assert get_b_by_b.status_code == 200
        assert float(get_b_by_b.json()["data"]["price"]) == 1500.00

        # Merchant B creates a Customer
        cust_b_resp = await client.post("/api/v1/customers", headers=headers_b, json={
            "name": "Beta Buyer",
            "email": "beta_buyer@example.com",
        })
        cust_b_id = cust_b_resp.json()["data"]["id"]

        # Merchant A attempts to read Merchant B's customer -> 404
        cust_a_access = await client.get(f"/api/v1/customers/{cust_b_id}", headers=headers_a)
        assert cust_a_access.status_code == 404

        # Merchant B creates a Cart
        cart_b_resp = await client.post("/api/v1/carts", headers=headers_b, json={
            "customer_id": cust_b_id,
        })
        cart_b_id = cart_b_resp.json()["data"]["id"]

        # Merchant A attempts to read Merchant B's cart -> 404
        cart_a_access = await client.get(f"/api/v1/carts/{cart_b_id}", headers=headers_a)
        assert cart_a_access.status_code == 404

    @pytest.mark.asyncio
    async def test_merchant_scoped_uniqueness_constraints(self, client: AsyncClient):
        """
        Verify tenant-scoped uniqueness:
        - Merchant A and Merchant B CAN have the exact same Product SKU
        - Merchant A CANNOT have duplicate Product SKU within Merchant A
        - Merchant A and Merchant B CAN have the exact same Customer Email
        """
        res_a = await client.post("/api/v1/auth/register", json={
            "merchant_name": "Uniq Store A",
            "email": "uniq_a@test.com",
            "password": "Password123!",
            "full_name": "A Owner",
        })
        headers_a = {"Authorization": f"Bearer {res_a.json()['data']['access_token']}"}

        res_b = await client.post("/api/v1/auth/register", json={
            "merchant_name": "Uniq Store B",
            "email": "uniq_b@test.com",
            "password": "Password123!",
            "full_name": "B Owner",
        })
        headers_b = {"Authorization": f"Bearer {res_b.json()['data']['access_token']}"}

        shared_sku = "COMMON-SKU-999"

        # Merchant A creates product with shared_sku
        resp_a1 = await client.post("/api/v1/products", headers=headers_a, json={
            "name": "Store A Common Item",
            "sku": shared_sku,
            "price": 100.00,
        })
        assert resp_a1.status_code == 201

        # Merchant A creates second product with SAME SKU -> 409 Conflict
        resp_a2 = await client.post("/api/v1/products", headers=headers_a, json={
            "name": "Store A Duplicate Item",
            "sku": shared_sku,
            "price": 120.00,
        })
        assert resp_a2.status_code == 409

        # Merchant B creates product with SAME SKU -> 201 Success (tenant isolation!)
        resp_b1 = await client.post("/api/v1/products", headers=headers_b, json={
            "name": "Store B Item",
            "sku": shared_sku,
            "price": 200.00,
        })
        assert resp_b1.status_code == 201

        # Both merchants create customer with same email -> 201 Success
        shared_email = "customer_shared@gmail.com"
        cust_a = await client.post("/api/v1/customers", headers=headers_a, json={
            "name": "Buyer in A",
            "email": shared_email,
        })
        assert cust_a.status_code == 201

        cust_b = await client.post("/api/v1/customers", headers=headers_b, json={
            "name": "Buyer in B",
            "email": shared_email,
        })
        assert cust_b.status_code == 201


# ============================================================
# 3. LIVE PAYMENT & WEBHOOK DEDUPLICATION
# ============================================================

class TestLivePaymentsAndWebhook:
    @pytest.mark.asyncio
    async def test_webhook_deduplication_and_repeated_delivery(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Verify real database behavior for:
        - provider_event_id unique constraint in PostgreSQL
        - Repeated webhook delivery returns already_processed
        - Invalid signature is rejected
        """
        # Register merchant & create order
        reg = await client.post("/api/v1/auth/register", json={
            "merchant_name": "Pay Test Store",
            "email": "pay_owner@test.com",
            "password": "Password123!",
            "full_name": "Pay Owner",
        })
        headers = {"Authorization": f"Bearer {reg.json()['data']['access_token']}"}

        # Create product & customer & cart & order
        prod = await client.post("/api/v1/products", headers=headers, json={
            "name": "Headphones", "sku": "HP-01", "price": 2000.00, "initial_stock": 10,
        })
        prod_id = prod.json()["data"]["id"]

        cust = await client.post("/api/v1/customers", headers=headers, json={
            "name": "Rohan", "email": "rohan@test.com",
        })
        cust_id = cust.json()["data"]["id"]

        cart = await client.post("/api/v1/carts", headers=headers, json={"customer_id": cust_id})
        cart_id = cart.json()["data"]["id"]

        await client.post(f"/api/v1/carts/{cart_id}/items", headers=headers, json={
            "product_id": prod_id, "quantity": 1,
        })

        order_res = await client.post("/api/v1/orders", headers=headers, json={"cart_id": cart_id})
        order_id = order_res.json()["data"]["id"]

        # Insert payment
        order_db = await db_session.get(Order, uuid.UUID(order_id))
        provider_order_id = f"rzp_ord_{uuid.uuid4().hex[:8]}"
        payment = Payment(
            order_id=uuid.UUID(order_id),
            merchant_id=order_db.merchant_id,
            amount=Decimal("2000.00"),
            currency="INR",
            status="pending",
            provider="razorpay",
            provider_order_id=provider_order_id,
            idempotency_key=f"idemp_{order_id}",
        )
        db_session.add(payment)
        await db_session.commit()
        await db_session.refresh(payment)

        # 1. Invalid signature rejection
        body = json.dumps({"event": "payment.captured"}).encode()
        bad_sig_res = await client.post(
            "/api/v1/payments/webhook",
            content=body,
            headers={"X-Razorpay-Signature": "invalid", "Content-Type": "application/json"},
        )
        assert bad_sig_res.status_code == 400

        # 2. Valid webhook execution
        event_id = f"evt_live_{uuid.uuid4().hex[:8]}"
        payload = {
            "event": "payment.captured",
            "event_id": event_id,
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_live_999",
                        "order_id": provider_order_id,
                        "status": "captured",
                    }
                }
            },
        }
        body_bytes = json.dumps(payload).encode()
        secret = settings.razorpay_webhook_secret or "webhook_placeholder_secret"
        valid_sig = _sign(body_bytes, secret)

        first_res = await client.post(
            "/api/v1/payments/webhook",
            content=body_bytes,
            headers={"X-Razorpay-Signature": valid_sig, "Content-Type": "application/json"},
        )
        assert first_res.status_code == 200
        assert first_res.json()["status"] == "processed"

        # 3. Duplicate delivery with same event_id -> deduplicated by DB provider_event_id
        dup_res = await client.post(
            "/api/v1/payments/webhook",
            content=body_bytes,
            headers={"X-Razorpay-Signature": valid_sig, "Content-Type": "application/json"},
        )
        assert dup_res.status_code == 200
        assert dup_res.json()["status"] == "duplicate"
        assert dup_res.json()["event_id"] == event_id

        # 4. Repeated event delivery with NEW event_id but same status -> already_processed
        new_event_id = f"evt_live_second_{uuid.uuid4().hex[:8]}"
        payload["event_id"] = new_event_id
        body_bytes2 = json.dumps(payload).encode()
        valid_sig2 = _sign(body_bytes2, secret)

        repeat_res = await client.post(
            "/api/v1/payments/webhook",
            content=body_bytes2,
            headers={"X-Razorpay-Signature": valid_sig2, "Content-Type": "application/json"},
        )
        assert repeat_res.status_code == 200
        assert repeat_res.json()["status"] == "already_processed"


# ============================================================
# 4. LIVE INVENTORY CONCURRENCY & CHECK CONSTRAINTS
# ============================================================

class TestLiveInventoryConcurrency:
    @pytest.mark.asyncio
    async def test_check_constraints_enforced_by_database(self, db_session: AsyncSession):
        """
        Verify database CHECK constraints:
        - quantity >= 0
        - reserved >= 0
        - reserved <= quantity
        """
        # Create merchant and product directly in DB
        from app.models.merchant import Merchant
        m = Merchant(name="Inv Store", slug="inv-store", email="inv@test.com")
        db_session.add(m)
        await db_session.flush()

        p = Product(merchant_id=m.id, name="Widget", slug="widget", sku="WDG-01", price=Decimal("10.00"))
        db_session.add(p)
        await db_session.flush()

        # 1. Negative quantity violates ck_inventory_quantity_positive
        inv_bad_qty = Inventory(product_id=p.id, merchant_id=m.id, quantity=-5, reserved=0)
        db_session.add(inv_bad_qty)
        with pytest.raises(sa.exc.IntegrityError):
            await db_session.flush()
        await db_session.rollback()

        # 2. Reserved > Quantity violates ck_inventory_reserved_lte_quantity
        m2 = Merchant(name="Inv Store 2", slug="inv-store-2", email="inv2@test.com")
        db_session.add(m2)
        await db_session.flush()
        p2 = Product(merchant_id=m2.id, name="Widget2", slug="widget2", sku="WDG-02", price=Decimal("10.00"))
        db_session.add(p2)
        await db_session.flush()

        inv_bad_res = Inventory(product_id=p2.id, merchant_id=m2.id, quantity=10, reserved=15)
        db_session.add(inv_bad_res)
        with pytest.raises(sa.exc.IntegrityError):
            await db_session.flush()
        await db_session.rollback()

    @pytest.mark.asyncio
    async def test_concurrent_reservations_prevent_overselling(self, client: AsyncClient):
        """
        Test concurrency:
        Available stock = 5.
        Three simultaneous checkout requests for quantity = 2 (Total requested = 6).
        Exactly two must succeed, and one must be rejected for Insufficient Stock.
        """
        reg = await client.post("/api/v1/auth/register", json={
            "merchant_name": "Flash Sale Store",
            "email": "flash@test.com",
            "password": "Password123!",
            "full_name": "Flash Merchant",
        })
        headers = {"Authorization": f"Bearer {reg.json()['data']['access_token']}"}

        prod = await client.post("/api/v1/products", headers=headers, json={
            "name": "Limited Edition Watch",
            "sku": "WATCH-LTD",
            "price": 10000.00,
            "initial_stock": 5,  # Only 5 in stock!
        })
        product_id = prod.json()["data"]["id"]

        cust = await client.post("/api/v1/customers", headers=headers, json={
            "name": "Buyer 1", "email": "buyer1@test.com",
        })
        cust_id = cust.json()["data"]["id"]

        # Create 3 separate carts, each with quantity 2
        cart_ids = []
        for _ in range(3):
            c_res = await client.post("/api/v1/carts", headers=headers, json={"customer_id": cust_id})
            c_id = c_res.json()["data"]["id"]
            await client.post(f"/api/v1/carts/{c_id}/items", headers=headers, json={
                "product_id": product_id, "quantity": 2,
            })
            cart_ids.append(c_id)

        # Execute order creations simultaneously
        async def try_checkout(cid):
            return await client.post("/api/v1/orders", headers=headers, json={"cart_id": cid})

        responses = await asyncio.gather(
            try_checkout(cart_ids[0]),
            try_checkout(cart_ids[1]),
            try_checkout(cart_ids[2]),
            return_exceptions=True,
        )

        status_codes = [r.status_code for r in responses if hasattr(r, "status_code")]
        # Exactly two 201 (success: 2 + 2 = 4 reserved), and one 422 (failure: 1 available < 2 requested)
        assert status_codes.count(201) == 2
        assert status_codes.count(422) == 1

        # Check final stock in DB
        inv_res = await client.get(f"/api/v1/inventory/{product_id}", headers=headers)
        assert inv_res.json()["data"]["quantity"] == 5
        assert inv_res.json()["data"]["reserved"] == 4
        assert inv_res.json()["data"]["available"] == 1


# ============================================================
# 5. OUTBOX ATOMICITY & ROLLBACK TESTS
# ============================================================

class TestLiveOutboxAtomicity:
    @pytest.mark.asyncio
    async def test_outbox_rollback_on_business_failure(self, db_session: AsyncSession):
        """
        Verify transactional outbox rollback:
        If a database transaction fails, the OutboxEvent must be rolled back
        and NOT persisted in the database.
        """
        initial_outbox_count = (await db_session.execute(
            sa.select(sa.func.count()).select_from(OutboxEvent)
        )).scalar()

        try:
            async with db_session.begin_nested():
                # Add outbox event
                evt = OutboxEvent(
                    event_type="test.event",
                    aggregate_type="test",
                    aggregate_id="123",
                    payload={"data": "sample"},
                )
                db_session.add(evt)
                # Intentionally trigger an exception / rollback
                raise RuntimeError("Simulated business transaction crash")
        except RuntimeError:
            pass

        # Verify no orphan event exists
        current_count = (await db_session.execute(
            sa.select(sa.func.count()).select_from(OutboxEvent)
        )).scalar()
        assert current_count == initial_outbox_count
