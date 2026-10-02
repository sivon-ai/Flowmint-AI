"""
Unit and integration tests for Buyer Agent.
"""

from decimal import Decimal
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.agents.buyer_agent import BuyerAgent
from app.ai.providers.mock import MockLLMProvider
from app.ai.tools.base import ToolContext
from app.models.category import Category
from app.models.inventory import Inventory
from app.models.merchant import Merchant
from app.models.product import Product, ProductAttribute


class TestBuyerAgent:
    @pytest.mark.asyncio
    async def test_buyer_agent_search_products(
        self, db_session: AsyncSession, merchant: Merchant
    ):
        # Seed 2 products for merchant
        p1 = Product(
            merchant_id=merchant.id,
            name="Ultrabook 15 Laptop",
            slug="ultrabook-15",
            sku="LAP-001",
            price=Decimal("65000.00"),
            status="active",
        )
        db_session.add(p1)
        await db_session.flush()

        inv1 = Inventory(product_id=p1.id, merchant_id=merchant.id, quantity=10, reserved=2)
        db_session.add(inv1)
        await db_session.commit()

        # Run buyer agent
        provider = MockLLMProvider()
        agent = BuyerAgent(provider=provider)
        ctx = ToolContext(
            merchant_id=merchant.id,
            trace_id="trc_buyer_test_1",
            db=db_session,
            is_read_only=True,
        )

        result = await agent.execute("Find me a laptop under 70000", ctx)
        assert result.agent_name == "buyer_agent"
        assert result.action_plan is None  # Phase 2A guarantee
        assert len(result.tool_calls) >= 1
        assert result.tool_calls[0]["name"] == "search_products"
        assert "Ultrabook 15 Laptop" in result.response
        assert "65000" in result.response
        assert "8 units available" in result.response  # 10 qty - 2 res = 8 avail

    @pytest.mark.asyncio
    async def test_buyer_agent_anti_hallucination_empty_catalog(
        self, db_session: AsyncSession, merchant: Merchant
    ):
        # Empty catalog — searching for non-existent product
        provider = MockLLMProvider()
        agent = BuyerAgent(provider=provider)
        ctx = ToolContext(
            merchant_id=merchant.id,
            trace_id="trc_buyer_empty",
            db=db_session,
            is_read_only=True,
        )

        result = await agent.execute("Find me a smartphone under 10000", ctx)
        assert "no products matched" in result.response.lower()
        # Verify no invented SKU or price was fabricated
        assert "SKU:" not in result.response

    @pytest.mark.asyncio
    async def test_buyer_agent_check_inventory(
        self, db_session: AsyncSession, merchant: Merchant
    ):
        p = Product(
            merchant_id=merchant.id,
            name="Smart Watch X",
            slug="smart-watch-x",
            sku="SW-99",
            price=Decimal("4999.00"),
            status="active",
        )
        db_session.add(p)
        await db_session.flush()

        inv = Inventory(product_id=p.id, merchant_id=merchant.id, quantity=50, reserved=5)
        db_session.add(inv)
        await db_session.commit()

        provider = MockLLMProvider()
        agent = BuyerAgent(provider=provider)
        ctx = ToolContext(
            merchant_id=merchant.id,
            trace_id="trc_buyer_stock",
            db=db_session,
            is_read_only=True,
        )

        result = await agent.execute(f"Check stock for {p.id}", ctx)
        assert result.action_plan is None
        assert "Available for Purchase: 45" in result.response  # 50 - 5 = 45
        assert "Total Quantity: 50" in result.response
