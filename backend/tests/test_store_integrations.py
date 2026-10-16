"""
Flowmint AI — Store Connections, Ingestion, Onboarding, and Razorpay Tests.

Validates:
1. Onboarding status lifecycle (first login, connect store step, manual skip).
2. Shopify OAuth initialization & validation.
3. WooCommerce connection with SSRF defense.
4. Custom store connection & ingestion of products, customers, and orders.
5. Idempotent synchronization via StoreEntityMapping (no duplicate products/orders on re-sync).
6. Multi-tenant isolation: merchant B cannot view or disconnect merchant A's store.
7. Secure credential encryption: API responses never expose tokens or secrets.
8. Razorpay checkout backend signature verification (valid and invalid HMAC signatures).
9. Merchant payment configuration (test vs live modes, webhook receiver).
10. Store disconnection without deleting historical records.
"""

import base64
import hashlib
import hmac
import json
import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.customer import Customer
from app.models.inventory import Inventory
from app.models.merchant import Merchant
from app.models.order import Order
from app.core.encryption import encrypt_credentials
from app.models.governance import AuditLog
from app.models.payment import Payment
from app.models.product import Product
from app.models.store_connection import StoreConnection, StoreEntityMapping

settings = get_settings()


# ==========================================
# 1. ONBOARDING STATUS & REDIRECTION
# ==========================================

@pytest.mark.asyncio
async def test_onboarding_status_initial_new_merchant(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/api/v1/onboarding/status", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["onboarding_completed"] is False
    assert data["onboarding_step"] == "connect_store"
    assert data["store_connected"] is False
    assert data["active_store"] is None


@pytest.mark.asyncio
async def test_onboarding_skip_manual_setup(client: AsyncClient, auth_headers: dict):
    resp = await client.post("/api/v1/onboarding/skip", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["onboarding_completed"] is True
    assert data["onboarding_step"] == "completed"
    assert data["store_mode"] == "manual"
    assert data["store_connected"] is False

    # Verify status persists on subsequent get
    status_resp = await client.get("/api/v1/onboarding/status", headers=auth_headers)
    assert status_resp.status_code == 200
    assert status_resp.json()["data"]["onboarding_completed"] is True


# ==========================================
# 2. SHOPIFY OAUTH
# ==========================================

@pytest.mark.asyncio
async def test_shopify_auth_init_invalid_domain(client: AsyncClient, auth_headers: dict):
    resp = await client.post(
        "/api/v1/stores/shopify/authorize",
        headers=auth_headers,
        json={"shop_domain": "invalid@@domain!!"},
    )
    assert resp.status_code in (400, 422)


@pytest.mark.asyncio
async def test_shopify_auth_init_unconfigured_credentials(client: AsyncClient, auth_headers: dict, monkeypatch):
    monkeypatch.setattr(settings, "shopify_client_id", "")
    monkeypatch.setattr(settings, "shopify_client_secret", "")

    resp = await client.post(
        "/api/v1/stores/shopify/authorize",
        headers=auth_headers,
        json={"shop_domain": "my-cool-apparel.myshopify.com"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["configured"] is False
    assert "not configured" in data["message"].lower()


@pytest.mark.asyncio
async def test_shopify_auth_init_configured(client: AsyncClient, auth_headers: dict, monkeypatch):
    monkeypatch.setattr(settings, "shopify_client_id", "test_shopify_client_id")
    monkeypatch.setattr(settings, "shopify_client_secret", "test_shopify_client_secret")

    resp = await client.post(
        "/api/v1/stores/shopify/authorize",
        headers=auth_headers,
        json={"shop_domain": "my-cool-apparel.myshopify.com"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["configured"] is True
    assert "admin/oauth/authorize" in data["authorization_url"]
    assert "test_shopify_client_id" in data["authorization_url"]


# ==========================================
# 3. WOOCOMMERCE & SSRF PROTECTION
# ==========================================

@pytest.mark.asyncio
async def test_woocommerce_rejects_ssrf_private_ip(client: AsyncClient, auth_headers: dict):
    # Attempting to target private network / localhost / link-local addresses
    resp = await client.post(
        "/api/v1/stores/woocommerce/connect",
        headers=auth_headers,
        json={
            "store_url": "https://127.0.0.1:8080",
            "consumer_key": "ck_test1234567890",
            "consumer_secret": "cs_test1234567890",
        },
    )
    assert resp.status_code == 422
    body = resp.json()
    err_msg = body.get("detail") or body.get("errors", [{}])[0].get("message", "")
    assert "blocked for security" in err_msg.lower()


@pytest.mark.asyncio
async def test_woocommerce_connect_and_sync(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    # Mock httpx requests to WooCommerce REST API
    mock_products = [
        {
            "id": 101,
            "name": "Woo Linen Shirt",
            "sku": "WOO-SHIRT-01",
            "price": "2499.00",
            "regular_price": "2999.00",
            "stock_quantity": 40,
            "status": "publish",
            "description": "Breathable summer linen shirt",
        }
    ]
    mock_customers = [
        {
            "id": 201,
            "email": "rohit@example.in",
            "first_name": "Rohit",
            "last_name": "Verma",
            "billing": {"phone": "+919876543210"},
        }
    ]
    mock_orders = [
        {
            "id": 301,
            "number": "WC-1001",
            "total": "2499.00",
            "currency": "INR",
            "status": "completed",
            "billing": {"email": "rohit@example.in", "first_name": "Rohit", "last_name": "Verma"},
            "line_items": [
                {"id": 401, "name": "Woo Linen Shirt", "sku": "WOO-SHIRT-01", "quantity": 1, "price": "2499.00"}
            ],
        }
    ]

    async def mock_wc_get(url, *args, **kwargs):
        url_str = str(url)
        if "system_status" in url_str:
            return Response(200, json={"environment": {"version": "8.5.0"}})
        elif "products" in url_str:
            return Response(200, json=mock_products)
        elif "customers" in url_str:
            return Response(200, json=mock_customers)
        elif "orders" in url_str:
            return Response(200, json=mock_orders)
        return Response(404)

    with patch("httpx.AsyncClient.get", side_effect=mock_wc_get):
        resp = await client.post(
            "/api/v1/stores/woocommerce/connect",
            headers=auth_headers,
            json={
                "store_url": "https://example.com/store",
                "consumer_key": "ck_test123456789012345",
                "consumer_secret": "cs_test123456789012345",
                "store_name": "Example Apparel",
            },
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["provider"] == "woocommerce"
        assert data["status"] == "connected"
        assert data["sync_status"] == "completed"
        # Secrets must NOT be returned in API response
        assert "consumer_secret" not in data
        assert "encrypted_credentials" not in data

        # Verify synced entities in database
        p_stmt = select(Product).where(Product.sku == "WOO-SHIRT-01")
        prod = (await db_session.execute(p_stmt)).scalar_one_or_none()
        assert prod is not None
        assert prod.name == "Woo Linen Shirt"
        assert prod.price == Decimal("2499.00")

        # Verify customer created
        c_stmt = select(Customer).where(Customer.email == "rohit@example.in")
        cust = (await db_session.execute(c_stmt)).scalar_one_or_none()
        assert cust is not None
        assert "Rohit" in cust.name

        # Verify order created
        o_stmt = select(Order).where(Order.order_number == "WC-1001")
        order = (await db_session.execute(o_stmt)).scalar_one_or_none()
        assert order is not None
        assert order.total == Decimal("2499.00")
        assert order.status == "completed"


# ==========================================
# 4. CUSTOM STORE INGESTION & IDEMPOTENCY
# ==========================================

@pytest.mark.asyncio
async def test_custom_store_connect_and_idempotent_ingestion(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession
):
    # 1. Connect Custom Store
    resp = await client.post(
        "/api/v1/stores/custom/connect",
        headers=auth_headers,
        json={
            "store_name": "Next.js Custom Headless",
            "store_url": "https://headless.example.com",
        },
    )
    assert resp.status_code == 200
    res_data = resp.json()["data"]
    connection_id = res_data["connection"]["id"]
    api_key = res_data["ingestion_api_key"]
    assert api_key.startswith("flw_live_")

    # 2. Ingest Products
    prod_payload = {
        "products": [
            {
                "external_id": "ext_prod_001",
                "name": "Ergonomic Mechanical Keyboard",
                "sku": "KB-MECH-01",
                "price": 8999.00,
                "quantity": 15,
                "status": "active",
            }
        ]
    }
    p_resp = await client.post(
        f"/api/v1/stores/custom/{connection_id}/ingest/products",
        headers=auth_headers,
        json=prod_payload,
    )
    assert p_resp.status_code == 200
    assert p_resp.json()["data"]["records_processed"] == 1

    # 3. Re-ingest the SAME product with updated price — must NOT create duplicate
    prod_payload_updated = {
        "products": [
            {
                "external_id": "ext_prod_001",
                "name": "Ergonomic Mechanical Keyboard (V2)",
                "sku": "KB-MECH-01",
                "price": 7999.00,
                "quantity": 25,
                "status": "active",
            }
        ]
    }
    p_resp2 = await client.post(
        f"/api/v1/stores/custom/{connection_id}/ingest/products",
        headers=auth_headers,
        json=prod_payload_updated,
    )
    assert p_resp2.status_code == 200

    # Verify only ONE product exists in DB with updated values
    all_prods = (
        await db_session.execute(select(Product).where(Product.sku == "KB-MECH-01"))
    ).scalars().all()
    assert len(all_prods) == 1
    assert all_prods[0].name == "Ergonomic Mechanical Keyboard (V2)"
    assert all_prods[0].price == Decimal("7999.00")

    # 4. Ingest Customer & Order
    cust_payload = {
        "customers": [
            {
                "external_id": "ext_cust_001",
                "email": "priya@example.in",
                "name": "Priya Sharma",
                "phone": "+919988776655",
            }
        ]
    }
    c_resp = await client.post(
        f"/api/v1/stores/custom/{connection_id}/ingest/customers",
        headers=auth_headers,
        json=cust_payload,
    )
    assert c_resp.status_code == 200

    order_payload = {
        "orders": [
            {
                "external_id": "ext_ord_001",
                "order_number": "FLW-NEXT-9001",
                "customer_email": "priya@example.in",
                "customer_name": "Priya Sharma",
                "total": 7999.00,
                "status": "confirmed",
                "items": [
                    {
                        "name": "Ergonomic Mechanical Keyboard (V2)",
                        "sku": "KB-MECH-01",
                        "quantity": 1,
                        "price": 7999.00,
                    }
                ],
            }
        ]
    }
    o_resp = await client.post(
        f"/api/v1/stores/custom/{connection_id}/ingest/orders",
        headers=auth_headers,
        json=order_payload,
    )
    assert o_resp.status_code == 200

    # 5. Verify Store Sync Summary updated
    conn_resp = await client.get(f"/api/v1/stores/{connection_id}", headers=auth_headers)
    assert conn_resp.status_code == 200
    summary = conn_resp.json()["data"]["sync_summary"]
    assert summary["products"] >= 1
    assert summary["customers"] >= 1
    assert summary["orders"] >= 1


# ==========================================
# 5. TENANT ISOLATION
# ==========================================

@pytest.mark.asyncio
async def test_tenant_isolation_store_connection(
    client: AsyncClient, auth_headers: dict, auth_headers_b: dict
):
    # Merchant A connects custom store
    resp = await client.post(
        "/api/v1/stores/custom/connect",
        headers=auth_headers,
        json={"store_name": "Merchant A Store", "store_url": "https://a.example.com"},
    )
    conn_id_a = resp.json()["data"]["connection"]["id"]

    # Merchant B cannot access Merchant A's store
    get_b = await client.get(f"/api/v1/stores/{conn_id_a}", headers=auth_headers_b)
    assert get_b.status_code == 404

    # Merchant B cannot disconnect Merchant A's store
    disc_b = await client.post(f"/api/v1/stores/{conn_id_a}/disconnect", headers=auth_headers_b)
    assert disc_b.status_code == 404

    # Merchant B cannot ingest into Merchant A's store
    ingest_b = await client.post(
        f"/api/v1/stores/custom/{conn_id_a}/ingest/products",
        headers=auth_headers_b,
        json={"products": []},
    )
    assert ingest_b.status_code == 404


# ==========================================
# 6. RAZORPAY CHECKOUT & VERIFICATION
# ==========================================

@pytest.mark.asyncio
async def test_razorpay_payment_config_get_and_update(client: AsyncClient, auth_headers: dict):
    # Get config
    get_res = await client.get("/api/v1/payments/config", headers=auth_headers)
    assert get_res.status_code == 200
    assert "webhook_url" in get_res.json()["data"]

    # Update config
    update_res = await client.post(
        "/api/v1/payments/config",
        headers=auth_headers,
        json={
            "payment_mode": "razorpay_hosted",
            "razorpay_key_id": "rzp_test_merchant_custom_key",
            "razorpay_key_secret": "custom_secret_1234567890",
            "razorpay_mode": "test",
        },
    )
    assert update_res.status_code == 200
    data = update_res.json()["data"]
    assert data["payment_mode"] == "razorpay_hosted"
    assert data["razorpay_configured"] is True
    # Secret must never be returned!
    assert "razorpay_key_secret" not in data


@pytest.mark.asyncio
async def test_razorpay_checkout_signature_verification(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession, product: Product, customer: Customer
):
    # 1. Create Cart
    cart_res = await client.post("/api/v1/carts", headers=auth_headers, json={"customer_id": None})
    cart_id = cart_res.json()["data"]["id"]

    await client.post(
        f"/api/v1/carts/{cart_id}/items",
        headers=auth_headers,
        json={"product_id": str(product.id), "quantity": 1},
    )

    # 2. Create Order
    order_res = await client.post(
        "/api/v1/orders", headers=auth_headers, json={"cart_id": cart_id}
    )
    assert order_res.status_code == 201
    order_id = uuid.UUID(order_res.json()["data"]["id"])

    # 3. Create simulated Razorpay order & Payment record
    provider_order_id = f"order_{uuid.uuid4().hex[:14]}"
    payment = Payment(
        order_id=order_id,
        merchant_id=product.merchant_id,
        amount=product.price,
        currency="INR",
        status="pending",
        provider="razorpay",
        provider_order_id=provider_order_id,
        idempotency_key=f"pay_test_{uuid.uuid4().hex[:8]}",
    )
    db_session.add(payment)
    await db_session.commit()
    await db_session.refresh(payment)

    # 4. Reject invalid signature
    bad_verify_res = await client.post(
        "/api/v1/payments/verify",
        headers=auth_headers,
        json={
            "payment_id": str(payment.id),
            "razorpay_order_id": provider_order_id,
            "razorpay_payment_id": "pay_fake_12345",
            "razorpay_signature": "invalid_signature_hex",
        },
    )
    assert bad_verify_res.status_code == 400

    # 5. Create fresh payment record to verify valid signature using backend HMAC SHA256
    provider_order_id_2 = f"order_{uuid.uuid4().hex[:14]}"
    payment_2 = Payment(
        order_id=order_id,
        merchant_id=product.merchant_id,
        amount=product.price,
        currency="INR",
        status="pending",
        provider="razorpay",
        provider_order_id=provider_order_id_2,
        idempotency_key=f"pay_test_{uuid.uuid4().hex[:8]}",
    )
    db_session.add(payment_2)
    await db_session.commit()
    await db_session.refresh(payment_2)

    valid_payment_id = "pay_test_valid_9988"
    msg = f"{provider_order_id_2}|{valid_payment_id}".encode("utf-8")
    valid_signature = hmac.new(
        settings.razorpay_key_secret.encode("utf-8"), msg, hashlib.sha256
    ).hexdigest()

    good_verify_res = await client.post(
        "/api/v1/payments/verify",
        headers=auth_headers,
        json={
            "payment_id": str(payment_2.id),
            "razorpay_order_id": provider_order_id_2,
            "razorpay_payment_id": valid_payment_id,
            "razorpay_signature": valid_signature,
        },
    )
    assert good_verify_res.status_code == 200
    res_data = good_verify_res.json()["data"]
    assert res_data["status"] == "captured"

    # Confirm order in DB transitioned to confirmed
    o_stmt = select(Order).where(Order.id == order_id)
    confirmed_order = (await db_session.execute(o_stmt)).scalar_one_or_none()
    assert confirmed_order.status == "confirmed"


# ==========================================
# 7. STORE DISCONNECT DATA PRESERVATION
# ==========================================

@pytest.mark.asyncio
async def test_store_disconnect_preserves_historical_records(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession
):
    # Connect store
    conn_res = await client.post(
        "/api/v1/stores/custom/connect",
        headers=auth_headers,
        json={"store_name": "Temporary Store", "store_url": "https://temp.example.com"},
    )
    conn_id = conn_res.json()["data"]["connection"]["id"]

    # Ingest product
    await client.post(
        f"/api/v1/stores/custom/{conn_id}/ingest/products",
        headers=auth_headers,
        json={
            "products": [
                {
                    "external_id": "temp_p1",
                    "name": "Historical Product",
                    "sku": "HIST-01",
                    "price": 1200.00,
                    "quantity": 10,
                }
            ]
        },
    )

    # Disconnect store
    disc_res = await client.post(f"/api/v1/stores/{conn_id}/disconnect", headers=auth_headers)
    assert disc_res.status_code == 200
    assert disc_res.json()["data"]["status"] == "disconnected"

    # Verify product STILL EXISTS (data preservation requirement)
    stmt = select(Product).where(Product.sku == "HIST-01")
    p = (await db_session.execute(stmt)).scalar_one_or_none()
    assert p is not None
    assert p.name == "Historical Product"


# ==========================================
# 8. SHOPIFY PRODUCT UPDATE SYNCHRONIZATION BUG & RESOLUTION
# ==========================================

def _make_shopify_hmac(body: bytes, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8")


@pytest.mark.asyncio
async def test_shopify_product_update_bug_reproduction_and_resolution(
    client: AsyncClient, auth_headers: dict, merchant: Merchant, db_session: AsyncSession, monkeypatch
):
    """
    Exact scenario requested by the user:
    1. A Shopify product initially has the name 'FM-TEST-001' with SKU 'FM-TEST-001'.
    2. Flowmint imports and stores that product.
    3. The product name is changed to 'FM-TEST' in Shopify, keeping SKU 'FM-TEST-001'.
    4. Shopify sends a verified update event (products/update).
    5. The existing Flowmint database record is updated in place.
    6. Flowmint still has exactly ONE corresponding imported product (no duplicates!).
    7. The Products API returns the new name 'FM-TEST'.
    """
    test_secret = "test-shopify-secret-webhook-987"
    monkeypatch.setattr(settings, "shopify_client_secret", test_secret)

    # 1. Create active Shopify connection for this merchant
    conn = StoreConnection(
        merchant_id=merchant.id,
        provider="shopify",
        store_url="https://flowmint-test-store.myshopify.com",
        store_name="flowmint-test-store",
        external_store_id="flowmint-test-store.myshopify.com",
        status="connected",
        encrypted_credentials="dummy_encrypted_creds",
    )
    db_session.add(conn)
    await db_session.commit()
    await db_session.refresh(conn)

    # 2. Initial product created in Shopify: name 'FM-TEST-001', SKU 'FM-TEST-001'
    initial_payload = {
        "id": 881234567,
        "title": "FM-TEST-001",
        "body_html": "<p>Initial description</p>",
        "status": "active",
        "variants": [
            {
                "id": 991234567,
                "sku": "FM-TEST-001",
                "price": "1499.00",
                "compare_at_price": "1999.00",
                "inventory_quantity": 25,
            }
        ],
    }
    raw_initial = json.dumps(initial_payload).encode("utf-8")
    hmac_initial = _make_shopify_hmac(raw_initial, test_secret)

    init_res = await client.post(
        "/api/v1/stores/shopify/webhook",
        content=raw_initial,
        headers={
            "X-Shopify-Topic": "products/create",
            "X-Shopify-Hmac-Sha256": hmac_initial,
            "X-Shopify-Shop-Domain": "flowmint-test-store.myshopify.com",
            "X-Shopify-Webhook-Id": str(uuid.uuid4()),
            "Content-Type": "application/json",
        },
    )
    assert init_res.status_code == 200

    # Verify product initially exists in Products API with old name
    get_res1 = await client.get("/api/v1/products", headers=auth_headers)
    assert get_res1.status_code == 200
    prods1 = get_res1.json()["data"]
    assert len(prods1) == 1
    assert prods1[0]["name"] == "FM-TEST-001"
    assert prods1[0]["sku"] == "FM-TEST-001"
    assert float(prods1[0]["price"]) == 1499.00
    assert prods1[0]["inventory"]["available"] == 25

    # 3. Product name is changed in Shopify from 'FM-TEST-001' to 'FM-TEST' (keeping SKU 'FM-TEST-001')
    update_payload = {
        "id": 881234567,
        "title": "FM-TEST",
        "body_html": "<p>Updated description for FM-TEST</p>",
        "status": "active",
        "variants": [
            {
                "id": 991234567,
                "sku": "FM-TEST-001",
                "price": "1599.00",
                "compare_at_price": "1999.00",
                "inventory_quantity": 30,
            }
        ],
    }
    raw_update = json.dumps(update_payload).encode("utf-8")
    hmac_update = _make_shopify_hmac(raw_update, test_secret)

    # 4. Shopify sends verified products/update webhook
    upd_res = await client.post(
        "/api/v1/stores/shopify/webhook",
        content=raw_update,
        headers={
            "X-Shopify-Topic": "products/update",
            "X-Shopify-Hmac-Sha256": hmac_update,
            "X-Shopify-Shop-Domain": "flowmint-test-store.myshopify.com",
            "X-Shopify-Webhook-Id": str(uuid.uuid4()),
            "Content-Type": "application/json",
        },
    )
    assert upd_res.status_code == 200
    assert upd_res.json()["data"]["name"] == "FM-TEST"

    # 5 & 6. Verify database contains EXACTLY ONE product (no duplicate!) with updated name
    db_prods = (
        await db_session.execute(
            select(Product).where(Product.merchant_id == merchant.id)
        )
    ).scalars().all()
    assert len(db_prods) == 1
    assert db_prods[0].name == "FM-TEST"
    assert db_prods[0].sku == "FM-TEST-001"
    assert db_prods[0].price == Decimal("1599.00")

    # 7. Products API returns the new name 'FM-TEST' immediately on fetch
    get_res2 = await client.get("/api/v1/products", headers=auth_headers)
    assert get_res2.status_code == 200
    prods2 = get_res2.json()["data"]
    assert len(prods2) == 1
    assert prods2[0]["name"] == "FM-TEST"
    assert float(prods2[0]["price"]) == 1599.00
    assert prods2[0]["inventory"]["available"] == 30


@pytest.mark.asyncio
async def test_shopify_webhook_invalid_signature_rejected(
    client: AsyncClient, merchant: Merchant, db_session: AsyncSession, monkeypatch
):
    monkeypatch.setattr(settings, "shopify_client_secret", "correct-secret")
    raw_payload = b'{"id": 12345, "title": "Tampered"}'

    # Send with bad signature
    resp = await client.post(
        "/api/v1/stores/shopify/webhook",
        content=raw_payload,
        headers={
            "X-Shopify-Topic": "products/update",
            "X-Shopify-Hmac-Sha256": "bad_invalid_hmac_signature==",
            "X-Shopify-Shop-Domain": "test-store.myshopify.com",
            "Content-Type": "application/json",
        },
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_shopify_webhook_deduplication(
    client: AsyncClient, merchant: Merchant, db_session: AsyncSession, monkeypatch
):
    test_secret = "secret-dedup"
    monkeypatch.setattr(settings, "shopify_client_secret", test_secret)

    conn = StoreConnection(
        merchant_id=merchant.id,
        provider="shopify",
        store_url="https://dedup-store.myshopify.com",
        store_name="dedup-store",
        external_store_id="dedup-store.myshopify.com",
        status="connected",
        encrypted_credentials="dummy_encrypted_creds",
    )
    db_session.add(conn)
    await db_session.commit()

    webhook_id = str(uuid.uuid4())
    payload = {"id": 77777, "title": "Dedup Item", "variants": [{"sku": "DEDUP-01", "price": "100.00"}]}
    raw_body = json.dumps(payload).encode("utf-8")
    hmac_val = _make_shopify_hmac(raw_body, test_secret)

    headers = {
        "X-Shopify-Topic": "products/create",
        "X-Shopify-Hmac-Sha256": hmac_val,
        "X-Shopify-Shop-Domain": "dedup-store.myshopify.com",
        "X-Shopify-Webhook-Id": webhook_id,
        "Content-Type": "application/json",
    }

    # First delivery: processed
    resp1 = await client.post("/api/v1/stores/shopify/webhook", content=raw_body, headers=headers)
    assert resp1.status_code == 200
    assert resp1.json()["data"]["status"] == "processed"

    # Second delivery (same webhook_id): duplicate ignored without error
    resp2 = await client.post("/api/v1/stores/shopify/webhook", content=raw_body, headers=headers)
    assert resp2.status_code == 200
    assert resp2.json()["data"]["status"] == "duplicate_ignored"


@pytest.mark.asyncio
async def test_shopify_webhook_product_delete_archives(
    client: AsyncClient, auth_headers: dict, merchant: Merchant, db_session: AsyncSession, monkeypatch
):
    test_secret = "secret-delete"
    monkeypatch.setattr(settings, "shopify_client_secret", test_secret)

    conn = StoreConnection(
        merchant_id=merchant.id,
        provider="shopify",
        store_url="https://del-store.myshopify.com",
        store_name="del-store",
        external_store_id="del-store.myshopify.com",
        status="connected",
        encrypted_credentials="dummy_encrypted_creds",
    )
    db_session.add(conn)
    await db_session.commit()

    # Create product via webhook
    create_payload = {"id": 55555, "title": "To Delete", "variants": [{"sku": "DEL-01", "price": "50.00"}]}
    raw_create = json.dumps(create_payload).encode("utf-8")
    await client.post(
        "/api/v1/stores/shopify/webhook",
        content=raw_create,
        headers={
            "X-Shopify-Topic": "products/create",
            "X-Shopify-Hmac-Sha256": _make_shopify_hmac(raw_create, test_secret),
            "X-Shopify-Shop-Domain": "del-store.myshopify.com",
            "Content-Type": "application/json",
        },
    )

    # Now send products/delete
    delete_payload = {"id": 55555}
    raw_del = json.dumps(delete_payload).encode("utf-8")
    del_res = await client.post(
        "/api/v1/stores/shopify/webhook",
        content=raw_del,
        headers={
            "X-Shopify-Topic": "products/delete",
            "X-Shopify-Hmac-Sha256": _make_shopify_hmac(raw_del, test_secret),
            "X-Shopify-Shop-Domain": "del-store.myshopify.com",
            "Content-Type": "application/json",
        },
    )
    assert del_res.status_code == 200
    assert del_res.json()["data"]["status"] == "archived"

    # Verify product in database has status == 'archived'
    p = (await db_session.execute(select(Product).where(Product.sku == "DEL-01"))).scalar_one_or_none()
    assert p is not None
    assert p.status == "archived"


@pytest.mark.asyncio
async def test_shopify_webhook_disconnected_store_rejected(
    client: AsyncClient, merchant: Merchant, db_session: AsyncSession, monkeypatch
):
    test_secret = "secret-disc"
    monkeypatch.setattr(settings, "shopify_client_secret", test_secret)

    conn = StoreConnection(
        merchant_id=merchant.id,
        provider="shopify",
        store_url="https://disc-store.myshopify.com",
        store_name="disc-store",
        external_store_id="disc-store.myshopify.com",
        status="disconnected",
        encrypted_credentials="dummy_encrypted_creds",
    )
    db_session.add(conn)
    await db_session.commit()

    payload = {"id": 99999, "title": "Disconnected Item"}
    raw_body = json.dumps(payload).encode("utf-8")
    res = await client.post(
        "/api/v1/stores/shopify/webhook",
        content=raw_body,
        headers={
            "X-Shopify-Topic": "products/update",
            "X-Shopify-Hmac-Sha256": _make_shopify_hmac(raw_body, test_secret),
            "X-Shopify-Shop-Domain": "disc-store.myshopify.com",
            "Content-Type": "application/json",
        },
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_product_local_edit_and_persistence(
    client: AsyncClient, auth_headers: dict, merchant: Merchant, db_session: AsyncSession
):
    """Test editing a local product updates all fields and persists accurately."""
    # 1. Create a local product
    create_res = await client.post(
        "/api/v1/products",
        headers=auth_headers,
        json={
            "name": "Local Keyboard",
            "sku": "KB-LOCAL-01",
            "price": 2499.00,
            "compare_at_price": 2999.00,
            "description": "Ergonomic mechanical keyboard",
            "initial_stock": 15,
            "currency": "INR",
        },
    )
    assert create_res.status_code == 201
    prod_id = create_res.json()["data"]["id"]

    # 2. Edit product locally
    patch_res = await client.patch(
        f"/api/v1/products/{prod_id}",
        headers=auth_headers,
        json={
            "name": "Local Keyboard Pro",
            "sku": "KB-LOCAL-01-PRO",
            "price": 2799.00,
            "compare_at_price": 3299.00,
            "inventory_quantity": 25,
            "description": "Pro edition with RGB lighting",
            "status": "active",
        },
    )
    assert patch_res.status_code == 200
    patched_data = patch_res.json()["data"]
    assert patched_data["name"] == "Local Keyboard Pro"
    assert patched_data["sku"] == "KB-LOCAL-01-PRO"
    assert float(patched_data["price"]) == 2799.00
    assert float(patched_data["compare_at_price"]) == 3299.00
    assert patched_data["inventory"]["available"] == 25
    assert patched_data["is_shopify_connected"] is False
    assert patched_data["shopify_sync_result"] is None

    # 3. Verify persistence on GET /api/v1/products/{id}
    get_res = await client.get(f"/api/v1/products/{prod_id}", headers=auth_headers)
    assert get_res.status_code == 200
    get_data = get_res.json()["data"]
    assert get_data["name"] == "Local Keyboard Pro"
    assert get_data["sku"] == "KB-LOCAL-01-PRO"
    assert float(get_data["price"]) == 2799.00
    assert get_data["inventory"]["available"] == 25


@pytest.mark.asyncio
async def test_shopify_product_edit_push_to_shopify_success(
    client: AsyncClient, auth_headers: dict, merchant: Merchant, db_session: AsyncSession, monkeypatch
):
    """
    Test editing a Shopify-connected product and pushing updates to Shopify via GraphQL Admin API.
    Verifies GraphQL mutations, audit trail recording, and persistence.
    """
    test_secret = "secret-bidirectional"
    monkeypatch.setattr(settings, "shopify_client_secret", test_secret)

    # 1. Connected Shopify store with write permissions
    conn = StoreConnection(
        merchant_id=merchant.id,
        provider="shopify",
        store_url="https://bidi-store.myshopify.com",
        store_name="bidi-store",
        external_store_id="bidi-store.myshopify.com",
        status="connected",
        scopes="read_products,write_products,read_inventory,write_inventory",
        encrypted_credentials=encrypt_credentials({"access_token": "shpat_test_token_999", "shop": "bidi-store.myshopify.com"}),
    )
    db_session.add(conn)
    await db_session.commit()
    await db_session.refresh(conn)

    # 2. Ingest product from Shopify
    init_payload = {
        "id": 55112233,
        "title": "Shopify Headphones",
        "variants": [{"id": 77112233, "sku": "SHP-HD-01", "price": "3999.00", "inventory_quantity": 20}],
    }
    raw_init = json.dumps(init_payload).encode("utf-8")
    init_res = await client.post(
        "/api/v1/stores/shopify/webhook",
        content=raw_init,
        headers={
            "X-Shopify-Topic": "products/create",
            "X-Shopify-Hmac-Sha256": _make_shopify_hmac(raw_init, test_secret),
            "X-Shopify-Shop-Domain": "bidi-store.myshopify.com",
            "Content-Type": "application/json",
        },
    )
    assert init_res.status_code == 200
    internal_id = init_res.json()["data"]["product_id"]

    # 3. Intercept outbound Shopify GraphQL requests
    orig_post = AsyncClient.post

    async def mock_shopify_post(self, url, **kwargs):
        url_str = str(url)
        if "admin/api" in url_str and "graphql.json" in url_str:
            q = kwargs.get("json", {}).get("query", "")
            if "getProductAndLocations" in q:
                return Response(
                    200,
                    json={
                        "data": {
                            "product": {
                                "id": "gid://shopify/Product/55112233",
                                "title": "Shopify Headphones",
                                "descriptionHtml": "<p>Old desc</p>",
                                "status": "ACTIVE",
                                "variants": {
                                    "nodes": [
                                        {
                                            "id": "gid://shopify/ProductVariant/77112233",
                                            "sku": "SHP-HD-01",
                                            "price": "3999.00",
                                            "compareAtPrice": None,
                                            "inventoryItem": {"id": "gid://shopify/InventoryItem/88112233"},
                                        }
                                    ]
                                },
                            },
                            "locations": {
                                "nodes": [
                                    {"id": "gid://shopify/Location/99112233", "name": "Primary Warehouse", "isActive": True}
                                ]
                            },
                        }
                    },
                )
            elif "productUpdate" in q:
                return Response(
                    200,
                    json={
                        "data": {
                            "productUpdate": {
                                "product": {"id": "gid://shopify/Product/55112233", "title": "Shopify Headphones Pro", "status": "ACTIVE"},
                                "userErrors": [],
                            }
                        }
                    },
                )
            elif "productVariantsBulkUpdate" in q:
                return Response(
                    200,
                    json={
                        "data": {
                            "productVariantsBulkUpdate": {
                                "productVariants": [
                                    {"id": "gid://shopify/ProductVariant/77112233", "sku": "SHP-HD-01", "price": "4499.00", "compareAtPrice": "4999.00"}
                                ],
                                "userErrors": [],
                            }
                        }
                    },
                )
            elif "inventorySetQuantities" in q:
                return Response(
                    200,
                    json={
                        "data": {
                            "inventorySetQuantities": {
                                "inventoryAdjustmentGroup": {"reason": "correction", "changes": []},
                                "userErrors": [],
                            }
                        }
                    },
                )
        return await orig_post(self, url, **kwargs)

    monkeypatch.setattr(AsyncClient, "post", mock_shopify_post)

    # 4. Patch product with sync_to_shopify=True
    patch_res = await client.patch(
        f"/api/v1/products/{internal_id}",
        headers=auth_headers,
        json={
            "name": "Shopify Headphones Pro",
            "price": 4499.00,
            "compare_at_price": 4999.00,
            "inventory_quantity": 40,
            "sync_to_shopify": True,
        },
    )
    assert patch_res.status_code == 200
    res_data = patch_res.json()["data"]
    assert res_data["name"] == "Shopify Headphones Pro"
    assert float(res_data["price"]) == 4499.00
    assert res_data["inventory"]["available"] == 40
    assert res_data["is_shopify_connected"] is True
    assert res_data["shopify_sync_result"] is not None
    assert res_data["shopify_sync_result"]["success"] is True
    assert res_data["shopify_sync_result"]["status"] == "pushed"

    # 5. Verify audit log entry was created
    audit_stmt = select(AuditLog).where(
        AuditLog.merchant_id == merchant.id,
        AuditLog.event_type == "product.shopify_synced",
    )
    audit = (await db_session.execute(audit_stmt)).scalar_one_or_none()
    assert audit is not None
    assert "Shopify Headphones Pro" in audit.reason


@pytest.mark.asyncio
async def test_shopify_product_edit_insufficient_permissions(
    client: AsyncClient, auth_headers: dict, merchant: Merchant, db_session: AsyncSession, monkeypatch
):
    """
    Test editing a Shopify product when the store connection only has read scopes.
    The local product update must succeed, but the push must safely fail with 'permission_denied'.
    """
    test_secret = "secret-perm"
    monkeypatch.setattr(settings, "shopify_client_secret", test_secret)

    # Read-only store connection (missing write_products)
    conn = StoreConnection(
        merchant_id=merchant.id,
        provider="shopify",
        store_url="https://readonly-store.myshopify.com",
        store_name="readonly-store",
        external_store_id="readonly-store.myshopify.com",
        status="connected",
        scopes="read_products,read_orders,read_inventory,read_customers",
        encrypted_credentials=encrypt_credentials({"access_token": "shpat_readonly", "shop": "readonly-store.myshopify.com"}),
    )
    db_session.add(conn)
    await db_session.commit()

    # Ingest product
    payload = {"id": 888111, "title": "Read Only Item", "variants": [{"sku": "RO-01", "price": "100.00"}]}
    raw_body = json.dumps(payload).encode("utf-8")
    init_res = await client.post(
        "/api/v1/stores/shopify/webhook",
        content=raw_body,
        headers={
            "X-Shopify-Topic": "products/create",
            "X-Shopify-Hmac-Sha256": _make_shopify_hmac(raw_body, test_secret),
            "X-Shopify-Shop-Domain": "readonly-store.myshopify.com",
            "Content-Type": "application/json",
        },
    )
    prod_id = init_res.json()["data"]["product_id"]

    # Attempt to push changes to Shopify
    patch_res = await client.patch(
        f"/api/v1/products/{prod_id}",
        headers=auth_headers,
        json={"name": "Read Only Updated", "sync_to_shopify": True},
    )
    assert patch_res.status_code == 200
    res_data = patch_res.json()["data"]

    # Local update succeeded
    assert res_data["name"] == "Read Only Updated"

    # Push to Shopify failed with permission_denied
    assert res_data["shopify_sync_result"]["success"] is False
    assert res_data["shopify_sync_result"]["status"] == "permission_denied"
    assert "write_products" in res_data["shopify_sync_result"]["message"]

    # Verify failure recorded in audit log
    audit_stmt = select(AuditLog).where(
        AuditLog.merchant_id == merchant.id,
        AuditLog.event_type == "product.shopify_sync_failed",
    )
    audit = (await db_session.execute(audit_stmt)).scalar_one_or_none()
    assert audit is not None


@pytest.mark.asyncio
async def test_shopify_product_edit_shopify_api_user_error(
    client: AsyncClient, auth_headers: dict, merchant: Merchant, db_session: AsyncSession, monkeypatch
):
    """
    Test when Shopify GraphQL returns a userError validation message (e.g. invalid title).
    Local update is committed, but Shopify push reports failure with user error.
    """
    test_secret = "secret-usererror"
    monkeypatch.setattr(settings, "shopify_client_secret", test_secret)

    conn = StoreConnection(
        merchant_id=merchant.id,
        provider="shopify",
        store_url="https://err-store.myshopify.com",
        store_name="err-store",
        external_store_id="err-store.myshopify.com",
        status="connected",
        scopes="read_products,write_products,read_inventory,write_inventory",
        encrypted_credentials=encrypt_credentials({"access_token": "shpat_err", "shop": "err-store.myshopify.com"}),
    )
    db_session.add(conn)
    await db_session.commit()

    payload = {"id": 999222, "title": "Err Item", "variants": [{"sku": "ERR-01", "price": "50.00"}]}
    raw_body = json.dumps(payload).encode("utf-8")
    init_res = await client.post(
        "/api/v1/stores/shopify/webhook",
        content=raw_body,
        headers={
            "X-Shopify-Topic": "products/create",
            "X-Shopify-Hmac-Sha256": _make_shopify_hmac(raw_body, test_secret),
            "X-Shopify-Shop-Domain": "err-store.myshopify.com",
            "Content-Type": "application/json",
        },
    )
    prod_id = init_res.json()["data"]["product_id"]

    orig_post = AsyncClient.post

    async def mock_err_post(self, url, **kwargs):
        url_str = str(url)
        if "admin/api" in url_str and "graphql.json" in url_str:
            q = kwargs.get("json", {}).get("query", "")
            if "getProductAndLocations" in q:
                return Response(
                    200,
                    json={
                        "data": {
                            "product": {"id": "gid://shopify/Product/999222", "title": "Err Item", "variants": {"nodes": []}},
                            "locations": {"nodes": []},
                        }
                    },
                )
            elif "productUpdate" in q:
                return Response(
                    200,
                    json={
                        "data": {
                            "productUpdate": {
                                "product": None,
                                "userErrors": [{"field": ["title"], "message": "Title cannot contain special characters"}],
                            }
                        }
                    },
                )
        return await orig_post(self, url, **kwargs)

    monkeypatch.setattr(AsyncClient, "post", mock_err_post)

    patch_res = await client.patch(
        f"/api/v1/products/{prod_id}",
        headers=auth_headers,
        json={"name": "Special @@ Item", "sync_to_shopify": True},
    )
    assert patch_res.status_code == 200
    res_data = patch_res.json()["data"]
    assert res_data["name"] == "Special @@ Item"
    assert res_data["shopify_sync_result"]["success"] is False
    assert res_data["shopify_sync_result"]["status"] == "failed"
    assert "Title cannot contain special characters" in str(res_data["shopify_sync_result"]["errors"])


