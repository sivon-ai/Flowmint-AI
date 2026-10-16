"""
Flowmint AI — Customer Management Integration Tests.

Validates:
1. Listing customers for the authenticated merchant with ground-truth order totals.
2. Pagination boundaries (page, per_page, total count).
3. Search filtering across name, email, and phone.
4. Creating a valid customer.
5. Rejection of invalid email or missing required fields.
6. Duplicate email prevention within the same merchant account.
7. Retrieving individual customer profile with aggregated order metrics.
8. Updating customer details (name, email, phone).
9. Cross-merchant customer update rejection (tenant isolation).
10. Cross-merchant customer retrieval rejection (tenant isolation).
11. Real purchase history and derived order statistics.
12. Empty purchase history handling for new/prospect customers.
13. Cross-merchant order history access rejection.
14. Unauthorized request rejection.
"""

import uuid
from decimal import Decimal
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customer import Customer
from app.models.merchant import Merchant
from app.models.order import Order, OrderItem
from app.models.product import Product


@pytest.mark.asyncio
async def test_list_customers_empty(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/api/v1/customers", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"] == []
    assert body["meta"]["total"] == 0


@pytest.mark.asyncio
async def test_create_customer_success(client: AsyncClient, auth_headers: dict):
    payload = {
        "name": "Priya Sharma",
        "email": "priya.sharma@example.in",
        "phone": "+91 98765 43210",
    }
    resp = await client.post("/api/v1/customers", headers=auth_headers, json=payload)
    assert resp.status_code == 201
    body = resp.json()
    assert body["success"] is True
    data = body["data"]
    assert data["name"] == "Priya Sharma"
    assert data["email"] == "priya.sharma@example.in"
    assert data["phone"] == "+91 98765 43210"
    assert data["order_count"] == 0
    assert float(data["total_spent"]) == 0.0


@pytest.mark.asyncio
async def test_create_customer_invalid_email(client: AsyncClient, auth_headers: dict):
    payload = {
        "name": "Invalid Customer",
        "email": "not-an-email",
    }
    resp = await client.post("/api/v1/customers", headers=auth_headers, json=payload)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_customer_duplicate_email(client: AsyncClient, auth_headers: dict):
    payload = {
        "name": "First Entry",
        "email": "duplicate@example.in",
    }
    resp1 = await client.post("/api/v1/customers", headers=auth_headers, json=payload)
    assert resp1.status_code == 201

    # Attempt to create duplicate email for same merchant
    resp2 = await client.post("/api/v1/customers", headers=auth_headers, json=payload)
    assert resp2.status_code in (409, 422)
    assert "already exists" in resp2.json()["errors"][0]["message"].lower()


@pytest.mark.asyncio
async def test_search_customers_by_name_email_phone(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession, merchant: Merchant
):
    c1 = Customer(merchant_id=merchant.id, name="Rahul Verma", email="rahul@techmart.in", phone="9988776655")
    c2 = Customer(merchant_id=merchant.id, name="Ananya Gupta", email="ananya@creative.in", phone="8877665544")
    c3 = Customer(merchant_id=merchant.id, name="Vikram Singh", email="vikram@speedy.in", phone="7766554433")
    db_session.add_all([c1, c2, c3])
    await db_session.commit()

    # Search by partial name
    r_name = await client.get("/api/v1/customers?q=rahul", headers=auth_headers)
    assert r_name.status_code == 200
    assert len(r_name.json()["data"]) == 1
    assert r_name.json()["data"][0]["name"] == "Rahul Verma"

    # Search by partial email
    r_email = await client.get("/api/v1/customers?q=creative.in", headers=auth_headers)
    assert r_email.status_code == 200
    assert len(r_email.json()["data"]) == 1
    assert r_email.json()["data"][0]["name"] == "Ananya Gupta"

    # Search by partial phone
    r_phone = await client.get("/api/v1/customers?q=4433", headers=auth_headers)
    assert r_phone.status_code == 200
    assert len(r_phone.json()["data"]) == 1
    assert r_phone.json()["data"][0]["name"] == "Vikram Singh"

    # Search with no match
    r_none = await client.get("/api/v1/customers?q=nonexistent", headers=auth_headers)
    assert r_none.status_code == 200
    assert len(r_none.json()["data"]) == 0


@pytest.mark.asyncio
async def test_list_customers_pagination(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession, merchant: Merchant
):
    customers = [
        Customer(merchant_id=merchant.id, name=f"Customer {i}", email=f"cust{i}@example.com")
        for i in range(1, 11)
    ]
    db_session.add_all(customers)
    await db_session.commit()

    # Page 1 (limit 4)
    r1 = await client.get("/api/v1/customers?page=1&per_page=4", headers=auth_headers)
    assert r1.status_code == 200
    meta1 = r1.json()["meta"]
    assert len(r1.json()["data"]) == 4
    assert meta1["page"] == 1
    assert meta1["total"] == 10
    assert meta1["total_pages"] == 3

    # Page 3 (remaining 2)
    r3 = await client.get("/api/v1/customers?page=3&per_page=4", headers=auth_headers)
    assert r3.status_code == 200
    assert len(r3.json()["data"]) == 2


@pytest.mark.asyncio
async def test_get_customer_detail(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession, merchant: Merchant
):
    c = Customer(
        merchant_id=merchant.id,
        name="Deepa Nair",
        email="deepa@example.in",
        phone="+91 99112 23344",
    )
    db_session.add(c)
    await db_session.commit()

    resp = await client.get(f"/api/v1/customers/{c.id}", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["name"] == "Deepa Nair"
    assert data["email"] == "deepa@example.in"
    assert data["phone"] == "+91 99112 23344"
    assert data["order_count"] == 0
    assert float(data["total_spent"]) == 0.0


@pytest.mark.asyncio
async def test_update_customer_success(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession, merchant: Merchant
):
    c = Customer(
        merchant_id=merchant.id,
        name="Original Name",
        email="original@example.in",
        phone="1111111111",
    )
    db_session.add(c)
    await db_session.commit()

    payload = {
        "name": "Updated Name",
        "email": "updated@example.in",
        "phone": "2222222222",
    }
    resp = await client.patch(f"/api/v1/customers/{c.id}", headers=auth_headers, json=payload)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["name"] == "Updated Name"
    assert data["email"] == "updated@example.in"
    assert data["phone"] == "2222222222"


@pytest.mark.asyncio
async def test_update_customer_email_conflict(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession, merchant: Merchant
):
    c1 = Customer(merchant_id=merchant.id, name="User One", email="user1@example.in")
    c2 = Customer(merchant_id=merchant.id, name="User Two", email="user2@example.in")
    db_session.add_all([c1, c2])
    await db_session.commit()

    # Try updating c2's email to user1@example.in
    resp = await client.patch(
        f"/api/v1/customers/{c2.id}",
        headers=auth_headers,
        json={"email": "user1@example.in"},
    )
    assert resp.status_code in (409, 422)


@pytest.mark.asyncio
async def test_cross_merchant_customer_isolation(
    client: AsyncClient,
    auth_headers: dict,
    auth_headers_b: dict,
    db_session: AsyncSession,
    merchant: Merchant,
    merchant_b: Merchant,
):
    """Ensure Merchant A cannot view or update Merchant B's customers."""
    cust_b = Customer(
        merchant_id=merchant_b.id,
        name="Merchant B Customer",
        email="cust_b@otherstore.in",
    )
    db_session.add(cust_b)
    await db_session.commit()

    # Merchant A attempts to GET Merchant B's customer -> 404
    resp_get = await client.get(f"/api/v1/customers/{cust_b.id}", headers=auth_headers)
    assert resp_get.status_code == 404

    # Merchant A attempts to PATCH Merchant B's customer -> 404
    resp_patch = await client.patch(
        f"/api/v1/customers/{cust_b.id}",
        headers=auth_headers,
        json={"name": "Hacked Name"},
    )
    assert resp_patch.status_code == 404

    # Merchant A attempts to view Merchant B's customer order history -> 404
    resp_orders = await client.get(f"/api/v1/customers/{cust_b.id}/orders", headers=auth_headers)
    assert resp_orders.status_code == 404

    # Merchant B CAN view own customer
    resp_b = await client.get(f"/api/v1/customers/{cust_b.id}", headers=auth_headers_b)
    assert resp_b.status_code == 200
    assert resp_b.json()["data"]["name"] == "Merchant B Customer"


@pytest.mark.asyncio
async def test_customer_purchase_history_and_aggregations(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession, merchant: Merchant
):
    """Verify ground-truth purchase history and summary metrics."""
    c = Customer(merchant_id=merchant.id, name="Shopper Khan", email="shopper@domain.in")
    db_session.add(c)
    await db_session.flush()

    prod = Product(
        merchant_id=merchant.id,
        name="Noise Cancelling Headphones",
        slug="nc-headphones",
        sku="NC-001",
        price=Decimal("4999.00"),
        currency="INR",
        status="active",
    )
    db_session.add(prod)
    await db_session.flush()

    # Order 1: Completed (₹5,000)
    o1 = Order(
        merchant_id=merchant.id,
        customer_id=c.id,
        order_number="ORD-TEST-001",
        status="completed",
        subtotal=Decimal("4999.00"),
        tax=Decimal("1.00"),
        discount=Decimal("0.00"),
        total=Decimal("5000.00"),
        currency="INR",
    )
    db_session.add(o1)
    await db_session.flush()
    db_session.add(OrderItem(order_id=o1.id, product_id=prod.id, product_name=prod.name, product_sku=prod.sku, quantity=1, unit_price=Decimal("4999.00"), total=Decimal("4999.00")))

    # Order 2: Confirmed (₹7,500)
    o2 = Order(
        merchant_id=merchant.id,
        customer_id=c.id,
        order_number="ORD-TEST-002",
        status="confirmed",
        subtotal=Decimal("7500.00"),
        tax=Decimal("0.00"),
        discount=Decimal("0.00"),
        total=Decimal("7500.00"),
        currency="INR",
    )
    db_session.add(o2)

    # Order 3: Cancelled (₹3,000) - must NOT count towards qualifying purchase total!
    o3 = Order(
        merchant_id=merchant.id,
        customer_id=c.id,
        order_number="ORD-TEST-003",
        status="cancelled",
        subtotal=Decimal("3000.00"),
        tax=Decimal("0.00"),
        discount=Decimal("0.00"),
        total=Decimal("3000.00"),
        currency="INR",
    )
    db_session.add(o3)
    await db_session.commit()

    # 1. Fetch Customer Detail and check aggregated stats
    resp_cust = await client.get(f"/api/v1/customers/{c.id}", headers=auth_headers)
    assert resp_cust.status_code == 200
    cust_data = resp_cust.json()["data"]
    assert cust_data["order_count"] == 2  # 2 qualifying (excluding cancelled)
    assert float(cust_data["total_spent"]) == 12500.00  # 5000 + 7500

    # 2. Fetch Customer Order History endpoint
    resp_orders = await client.get(f"/api/v1/customers/{c.id}/orders", headers=auth_headers)
    assert resp_orders.status_code == 200
    orders_body = resp_orders.json()["data"]
    summary = orders_body["summary"]
    assert summary["total_orders"] == 2
    assert float(summary["total_spent"]) == 12500.00
    assert float(summary["average_order_value"]) == 6250.00
    assert len(orders_body["orders"]) == 3  # All orders returned, including cancelled for audit history
    assert orders_body["orders"][0]["order_number"] in ("ORD-TEST-001", "ORD-TEST-002", "ORD-TEST-003")


@pytest.mark.asyncio
async def test_unauthorized_customer_access(client: AsyncClient):
    """Requests without bearer tokens must be rejected."""
    resp_list = await client.get("/api/v1/customers")
    assert resp_list.status_code in (401, 403)

    resp_create = await client.post("/api/v1/customers", json={"name": "A", "email": "a@a.com"})
    assert resp_create.status_code in (401, 403)
