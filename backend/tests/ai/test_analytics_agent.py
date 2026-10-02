"""
Unit and integration tests for Analytics Agent.
"""

from decimal import Decimal
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.agents.analytics_agent import AnalyticsAgent
from app.ai.providers.mock import MockLLMProvider
from app.ai.tools.base import ToolContext
from app.models.customer import Customer
from app.models.merchant import Merchant
from app.models.order import Order, OrderItem
from app.models.product import Product


class TestAnalyticsAgent:
    @pytest.mark.asyncio
    async def test_analytics_agent_revenue_summary(
        self, db_session: AsyncSession, merchant: Merchant
    ):
        # Seed customer and 2 paid orders
        cust = Customer(merchant_id=merchant.id, name="Test Customer", email="cust@test.com")
        db_session.add(cust)
        await db_session.flush()

        o1 = Order(
            merchant_id=merchant.id,
            customer_id=cust.id,
            order_number="FM-TEST-001",
            status="paid",
            subtotal=Decimal("2000.00"),
            total=Decimal("2000.00"),
            currency="INR",
        )
        o2 = Order(
            merchant_id=merchant.id,
            customer_id=cust.id,
            order_number="FM-TEST-002",
            status="completed",
            subtotal=Decimal("3000.00"),
            total=Decimal("3000.00"),
            currency="INR",
        )
        db_session.add_all([o1, o2])
        await db_session.commit()

        provider = MockLLMProvider()
        agent = AnalyticsAgent(provider=provider)
        ctx = ToolContext(
            merchant_id=merchant.id,
            trace_id="trc_analytics_rev_1",
            db=db_session,
            is_read_only=True,
        )

        result = await agent.execute("How much revenue was generated this month?", ctx)
        assert result.agent_name == "analytics_agent"
        assert result.action_plan is None  # Phase 2A guarantee
        assert len(result.tool_calls) >= 1
        assert result.tool_calls[0]["name"] == "get_revenue_summary"

        # Verify factual structure
        assert "Observed Facts" in result.response
        assert "Total Revenue: ₹5000.00" in result.response
        assert "Completed Orders: 2" in result.response
        assert "Average Order Value: ₹2500.00" in result.response
        assert "Derived Calculation & Interpretation" in result.response

    @pytest.mark.asyncio
    async def test_analytics_agent_product_performance(
        self, db_session: AsyncSession, merchant: Merchant
    ):
        cust = Customer(merchant_id=merchant.id, name="Cust 2", email="cust2@test.com")
        db_session.add(cust)
        await db_session.flush()

        order = Order(
            merchant_id=merchant.id,
            customer_id=cust.id,
            order_number="FM-PERF-01",
            status="paid",
            subtotal=Decimal("1500.00"),
            total=Decimal("1500.00"),
            currency="INR",
        )
        db_session.add(order)
        await db_session.flush()

        prod = Product(
            merchant_id=merchant.id,
            name="Top Selling Keyboard",
            slug="top-selling-keyboard",
            sku="KEY-01",
            price=Decimal("500.00"),
            status="active",
        )
        db_session.add(prod)
        await db_session.flush()

        item = OrderItem(
            order_id=order.id,
            product_id=prod.id,
            product_name="Top Selling Keyboard",
            product_sku="KEY-01",
            quantity=3,
            unit_price=Decimal("500.00"),
            total=Decimal("1500.00"),
        )
        db_session.add(item)
        await db_session.commit()

        provider = MockLLMProvider()
        agent = AnalyticsAgent(provider=provider)
        ctx = ToolContext(
            merchant_id=merchant.id,
            trace_id="trc_analytics_perf",
            db=db_session,
            is_read_only=True,
        )

        result = await agent.execute("Which are our top selling items?", ctx)
        assert result.action_plan is None
        assert "Top Selling Keyboard" in result.response
        assert "3 sold" in result.response
