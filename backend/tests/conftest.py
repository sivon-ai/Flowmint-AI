"""
Test fixtures for Flowmint AI backend tests.

Uses an in-memory or test database with real async sessions.
"""

import asyncio
import os
from pathlib import Path
import uuid
from collections.abc import AsyncGenerator
from decimal import Decimal

from dotenv import load_dotenv
import pytest
import pytest_asyncio
import sqlalchemy as sa
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

# Load backend/.env so pytest environment has FIREWORKS_API_KEY and other configured env vars
_env_path = Path(__file__).resolve().parent.parent / ".env"
if _env_path.exists():
    load_dotenv(dotenv_path=_env_path, override=False)

from app.config import get_settings
from app.core.security import create_access_token, hash_password
from app.database import Base, get_db
from app.main import app
from app.models.merchant import Merchant
from app.models.user import User
from app.models.category import Category
from app.models.product import Product, ProductAttribute
from app.models.inventory import Inventory
from app.models.customer import Customer


# Use the real database URL — tests run against the same DB
settings = get_settings()
TEST_DB_URL = settings.database_url

engine = create_async_engine(TEST_DB_URL, echo=False, poolclass=NullPool)
TestSessionFactory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

TABLES_TO_TRUNCATE = [
    "evaluation_benchmarks", "action_outcomes",
    "offers", "campaigns", "audit_logs", "action_executions", "approvals", "merchant_policies",
    "simulation_records", "action_plans", "opportunities",
    "tool_call_records", "agent_runs", "agent_messages", "agent_sessions",
    "outbox_events", "payment_events", "payments", "order_items", "orders",
    "cart_items", "carts", "customers", "inventory", "product_attributes",
    "products", "categories", "users", "merchants"
]



@pytest.fixture(autouse=True)
def isolate_mock_regression(monkeypatch):
    """
    Isolates standard regression tests to the deterministic MockLLM provider.
    Dedicated provider tests in test_fireworks_provider.py explicitly configure FireworksProvider.
    """
    s = get_settings()
    monkeypatch.setattr(s, "ai_provider", "mock")


@pytest_asyncio.fixture
async def setup_db():
    """Ensure clean database before and after each test."""
    async with engine.begin() as conn:
        await conn.execute(sa.text(f"TRUNCATE TABLE {', '.join(TABLES_TO_TRUNCATE)} CASCADE;"))
    yield
    async with engine.begin() as conn:
        await conn.execute(sa.text(f"TRUNCATE TABLE {', '.join(TABLES_TO_TRUNCATE)} CASCADE;"))


@pytest_asyncio.fixture
async def db_session(setup_db) -> AsyncGenerator[AsyncSession, None]:
    async with TestSessionFactory() as session:
        yield session


@pytest_asyncio.fixture
async def client(setup_db) -> AsyncGenerator[AsyncClient, None]:
    """HTTP test client with fresh DB session per request."""

    async def _override_get_db():
        async with TestSessionFactory() as session:
            yield session

    app.dependency_overrides[get_db] = _override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as c:
        yield c

    app.dependency_overrides.clear()


# --- Fixture Data ---

@pytest_asyncio.fixture
async def merchant(db_session: AsyncSession) -> Merchant:
    m = Merchant(
        name="Test Store",
        slug="test-store",
        email="test@flowmint.ai",
        status="active",
    )
    db_session.add(m)
    await db_session.commit()
    await db_session.refresh(m)
    return m


@pytest_asyncio.fixture
async def merchant_b(db_session: AsyncSession) -> Merchant:
    """Second merchant for cross-tenant isolation tests."""
    m = Merchant(
        name="Other Store",
        slug="other-store",
        email="other@flowmint.ai",
        status="active",
    )
    db_session.add(m)
    await db_session.commit()
    await db_session.refresh(m)
    return m


@pytest_asyncio.fixture
async def user(db_session: AsyncSession, merchant: Merchant) -> User:
    u = User(
        merchant_id=merchant.id,
        email="admin@flowmint.ai",
        hashed_password=hash_password("testpass123"),
        full_name="Test Admin",
        role="owner",
        is_active=True,
    )
    db_session.add(u)
    await db_session.commit()
    await db_session.refresh(u)
    return u


@pytest_asyncio.fixture
async def user_b(db_session: AsyncSession, merchant_b: Merchant) -> User:
    """User for the second merchant."""
    u = User(
        merchant_id=merchant_b.id,
        email="admin-b@flowmint.ai",
        hashed_password=hash_password("testpass123"),
        full_name="Other Admin",
        role="owner",
        is_active=True,
    )
    db_session.add(u)
    await db_session.commit()
    await db_session.refresh(u)
    return u


@pytest_asyncio.fixture
def auth_headers(user: User, merchant: Merchant) -> dict:
    token = create_access_token({
        "sub": str(user.id),
        "merchant_id": str(merchant.id),
        "role": user.role,
    })
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
def auth_headers_b(user_b: User, merchant_b: Merchant) -> dict:
    """Auth headers for the second merchant."""
    token = create_access_token({
        "sub": str(user_b.id),
        "merchant_id": str(merchant_b.id),
        "role": user_b.role,
    })
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def category(db_session: AsyncSession, merchant: Merchant) -> Category:
    c = Category(
        merchant_id=merchant.id,
        name="Electronics",
        slug="electronics",
    )
    db_session.add(c)
    await db_session.commit()
    await db_session.refresh(c)
    return c


@pytest_asyncio.fixture
async def product(db_session: AsyncSession, merchant: Merchant, category: Category) -> Product:
    p = Product(
        merchant_id=merchant.id,
        category_id=category.id,
        name="Test Laptop",
        slug="test-laptop",
        description="A great laptop for testing",
        sku="LAP-001",
        price=Decimal("59999.00"),
        status="active",
    )
    db_session.add(p)
    await db_session.flush()

    # Add inventory
    inv = Inventory(
        product_id=p.id,
        merchant_id=merchant.id,
        quantity=50,
        reserved=0,
    )
    db_session.add(inv)

    # Add attributes
    db_session.add(ProductAttribute(product_id=p.id, key="RAM", value="16GB"))
    db_session.add(ProductAttribute(product_id=p.id, key="Storage", value="512GB SSD"))

    await db_session.commit()
    await db_session.refresh(p)
    return p


@pytest_asyncio.fixture
async def customer(db_session: AsyncSession, merchant: Merchant) -> Customer:
    c = Customer(
        merchant_id=merchant.id,
        email="buyer@test.com",
        name="Test Buyer",
        phone="+919876543210",
    )
    db_session.add(c)
    await db_session.commit()
    await db_session.refresh(c)
    return c


def pytest_sessionfinish(session, exitstatus):
    """Restore canonical demo seed after test execution so merchant pages remain populated."""
    from app.seed import seed
    try:
        asyncio.run(seed())
    except Exception as e:
        pass

