"""
Flowmint AI — Decision Engine, Growth Agent, Recovery Agent & API Tests (Phase 2B).
Tests:
- Growth Agent recommendation-only execution and ActionPlan creation
- Recovery Agent recommendation-only execution and ActionPlan creation
- Zero write tools invariant
- ActionPlan schema validation
- Multi-tenant isolation for opportunities and action plans
- FastApi endpoints for opportunities, simulations, action-plans, and agents
"""

from decimal import Decimal
import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.agents.growth_agent import GrowthAgent
from app.ai.agents.recovery_agent import RecoveryAgent
from app.ai.providers.mock import MockLLMProvider
from app.ai.tools.base import ToolContext
from app.ai.tools.registry import tool_registry
from app.models.cart import Cart, CartItem
from app.models.customer import Customer
from app.models.merchant import Merchant
from app.models.opportunity import ActionPlan, ActionPlanStatus, Opportunity, OpportunityStatus, OpportunityType
from app.models.order import Order, OrderItem
from app.models.payment import Payment
from app.models.product import Product


class TestPhase2BDecisionEngine:

    @pytest.mark.asyncio
    async def test_growth_agent_bundle_recommendation(
        self, db_session: AsyncSession, merchant: Merchant
    ):
        cust = Customer(merchant_id=merchant.id, name="Growth Buyer", email="gb@test.com")
        db_session.add(cust)
        await db_session.flush()

        p1 = Product(merchant_id=merchant.id, name="Gaming Mouse", slug="gaming-mouse", sku="GM-01", price=Decimal("1500.00"), status="active")
        p2 = Product(merchant_id=merchant.id, name="Mouse Pad XL", slug="mouse-pad-xl", sku="PAD-01", price=Decimal("800.00"), status="active")
        db_session.add_all([p1, p2])
        await db_session.flush()

        # Seed co-purchases
        for i in range(2):
            o = Order(merchant_id=merchant.id, customer_id=cust.id, order_number=f"FM-GROWTH-{i}", status="paid", subtotal=Decimal("2300.00"), total=Decimal("2300.00"), currency="INR")
            db_session.add(o)
            await db_session.flush()
            db_session.add(OrderItem(order_id=o.id, product_id=p1.id, product_name="Gaming Mouse", product_sku="GM-01", quantity=1, unit_price=Decimal("1500.00"), total=Decimal("1500.00")))
            db_session.add(OrderItem(order_id=o.id, product_id=p2.id, product_name="Mouse Pad XL", product_sku="PAD-01", quantity=1, unit_price=Decimal("800.00"), total=Decimal("800.00")))
        await db_session.commit()

        provider = MockLLMProvider()
        agent = GrowthAgent(provider=provider)
        ctx = ToolContext(merchant_id=merchant.id, trace_id="trc_growth_01", db=db_session, is_read_only=True)

        result = await agent.execute("Recommend cross-sell bundles for our catalog", ctx)

        assert "Gaming Mouse" in result.response or "Mouse Pad" in result.response
        assert result.action_plan is not None
        assert result.action_plan["action_type"] == "cross_sell_bundle"
        assert result.action_plan["status"] == ActionPlanStatus.PROPOSED.value
        assert result.action_plan["requires_approval"] is True
        assert result.action_plan["action_id"] is not None

    @pytest.mark.asyncio
    async def test_recovery_agent_abandoned_cart_recommendation(
        self, db_session: AsyncSession, merchant: Merchant
    ):
        cust = Customer(merchant_id=merchant.id, name="Cart Dropper", email="dropper2@test.com")
        db_session.add(cust)
        await db_session.flush()

        prod = Product(merchant_id=merchant.id, name="Noise Cancelling Headphones", slug="nc-headphones", sku="NC-01", price=Decimal("7999.00"), status="active")
        db_session.add(prod)
        await db_session.flush()

        cart = Cart(merchant_id=merchant.id, customer_id=cust.id, status="active")
        db_session.add(cart)
        await db_session.flush()
        db_session.add(CartItem(cart_id=cart.id, product_id=prod.id, quantity=1, unit_price=Decimal("7999.00")))
        await db_session.commit()

        provider = MockLLMProvider()
        agent = RecoveryAgent(provider=provider)
        ctx = ToolContext(merchant_id=merchant.id, trace_id="trc_recovery_01", db=db_session, is_read_only=True)

        result = await agent.execute("Analyze abandoned carts and propose recovery strategy", ctx)

        assert "Noise Cancelling Headphones" in result.response or "7,999" in result.response or "abandoned" in result.response.lower()
        assert result.action_plan is not None
        assert result.action_plan["action_type"] == "abandoned_cart_recovery"
        assert result.action_plan["status"] == ActionPlanStatus.PROPOSED.value
        assert result.action_plan["requires_approval"] is True

    @pytest.mark.asyncio
    async def test_no_write_tools_in_registry_phase2b(self):
        """Verifies that every single tool registered in the platform is strictly read-only."""
        for name, tool in tool_registry.tools.items():
            assert tool.is_read_only is True, f"Tool '{name}' violates read-only safety invariant in Phase 2B!"
            assert "delete" not in name.lower()
            assert "create_campaign" not in name.lower()
            assert "apply_discount" not in name.lower()
            assert "issue_refund" not in name.lower()

    @pytest.mark.asyncio
    async def test_tenant_isolation_opportunities_and_action_plans(
        self, client: AsyncClient, auth_headers: dict, merchant: Merchant, merchant_b: Merchant, db_session: AsyncSession
    ):
        # Create opportunity for merchant_b
        opp_b = Opportunity(
            merchant_id=merchant_b.id,
            type=OpportunityType.ABANDONED_CART.value,
            title="Merchant B Secret Carts",
            description="Private data of merchant B",
            status=OpportunityStatus.DETECTED.value,
            estimated_value=Decimal("50000.00"),
            currency="INR",
            evidence_json={"secret": "merchant_b_only"},
        )
        db_session.add(opp_b)
        await db_session.commit()

        # Merchant A attempts to access Merchant B's opportunity via API
        resp = await client.get(f"/api/v1/opportunities/{opp_b.id}", headers=auth_headers)
        assert resp.status_code == 404

        # Merchant A lists opportunities
        list_resp = await client.get("/api/v1/opportunities?auto_detect=false", headers=auth_headers)
        assert list_resp.status_code == 200
        data = list_resp.json()["data"]
        assert all(o["id"] != str(opp_b.id) for o in data)

    @pytest.mark.asyncio
    async def test_api_opportunities_investigate_and_overview(
        self, client: AsyncClient, auth_headers: dict, merchant: Merchant, db_session: AsyncSession
    ):
        # Seed test customer and abandoned cart
        cust = Customer(merchant_id=merchant.id, name="Api Buyer", email="api_buyer@test.com")
        db_session.add(cust)
        await db_session.flush()

        prod = Product(merchant_id=merchant.id, name="Smart Watch", slug="smart-watch", sku="SW-01", price=Decimal("5500.00"), status="active")
        db_session.add(prod)
        await db_session.flush()

        cart = Cart(merchant_id=merchant.id, customer_id=cust.id, status="active")
        db_session.add(cart)
        await db_session.flush()
        db_session.add(CartItem(cart_id=cart.id, product_id=prod.id, quantity=1, unit_price=Decimal("5500.00")))
        await db_session.commit()

        # 1. GET /api/v1/opportunities/metrics/overview
        overview_resp = await client.get("/api/v1/opportunities/metrics/overview", headers=auth_headers)
        assert overview_resp.status_code == 200
        overview_data = overview_resp.json()["data"]
        assert overview_data["abandoned_cart_count"] == 1
        assert overview_data["abandoned_cart_value"] == 5500.0

        # 2. GET /api/v1/opportunities (triggers auto-detection)
        list_resp = await client.get("/api/v1/opportunities", headers=auth_headers)
        assert list_resp.status_code == 200
        opps = list_resp.json()["data"]
        assert len(opps) >= 1
        target_opp = opps[0]

        # 3. POST /api/v1/opportunities/{id}/investigate
        inv_resp = await client.post(f"/api/v1/opportunities/{target_opp['id']}/investigate", headers=auth_headers)
        assert inv_resp.status_code == 200
        inv_data = inv_resp.json()["data"]
        assert inv_data["status"] == "investigating"
        assert len(inv_data["investigation_notes"]) > 0

    @pytest.mark.asyncio
    async def test_api_what_if_simulations(
        self, client: AsyncClient, auth_headers: dict, merchant: Merchant, db_session: AsyncSession
    ):
        # 1. POST /api/v1/simulations/recovery
        rec_sim = await client.post(
            "/api/v1/simulations/recovery",
            headers=auth_headers,
            json={"discount_percent": 10.0, "min_cart_value": 1000.0, "assumed_conversion_rate": 0.20},
        )
        assert rec_sim.status_code == 200
        rec_data = rec_sim.json()["data"]
        assert rec_data["simulation_type"] == "cart_recovery"
        assert "projected_net_revenue" in rec_data["results"]
        assert "SIMULATION / ESTIMATE" in rec_data["results"]["disclaimer"]

        # 2. POST /api/v1/simulations/offer
        offer_sim = await client.post(
            "/api/v1/simulations/offer",
            headers=auth_headers,
            json={"discount_percent": 15.0, "expected_conversion_lift_pct": 25.0},
        )
        assert offer_sim.status_code == 200
        offer_data = offer_sim.json()["data"]
        assert offer_data["simulation_type"] == "offer_discount"
        assert "net_revenue_delta" in offer_data["results"]

    @pytest.mark.asyncio
    async def test_api_growth_and_recovery_agents(
        self, client: AsyncClient, auth_headers: dict, merchant: Merchant, db_session: AsyncSession
    ):
        # POST /api/v1/agents/growth
        growth_resp = await client.post(
            "/api/v1/agents/growth",
            headers=auth_headers,
            json={"message": "Analyze bundle opportunities for my store"},
        )
        assert growth_resp.status_code == 200
        growth_data = growth_resp.json()["data"]
        assert growth_data["agent_name"] == "growth_agent"

        # POST /api/v1/agents/recovery
        rec_resp = await client.post(
            "/api/v1/agents/recovery",
            headers=auth_headers,
            json={"message": "Propose abandoned cart recovery actions"},
        )
        assert rec_resp.status_code == 200
        rec_data = rec_resp.json()["data"]
        assert rec_data["agent_name"] == "recovery_agent"

        # GET /api/v1/action-plans
        plans_resp = await client.get("/api/v1/action-plans", headers=auth_headers)
        assert plans_resp.status_code == 200
