"""
Flowmint AI — Revenue Intelligence & Opportunity Detection Tests (Phase 2B).
Tests:
- Deterministic metrics calculation (revenue, AOV, carts, conversion, risk)
- Opportunity detectors (abandoned cart, payment failure, conversion drop, cross sell)
- Evidence inspectability and accuracy
- What-if simulation deterministic arithmetic
"""

from decimal import Decimal
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cart import Cart, CartItem
from app.models.customer import Customer
from app.models.merchant import Merchant
from app.models.opportunity import Opportunity, OpportunityStatus, OpportunityType
from app.models.order import Order, OrderItem
from app.models.payment import Payment
from app.models.product import Product
from app.services.opportunity_engine import OpportunityEngine
from app.services.revenue_intelligence import RevenueIntelligenceService
from app.services.simulation_engine import WhatIfSimulationService


class TestRevenueIntelligenceAndOpportunities:

    @pytest.mark.asyncio
    async def test_revenue_intelligence_overview_metrics(
        self, db_session: AsyncSession, merchant: Merchant
    ):
        # 1. Seed Customer
        cust = Customer(merchant_id=merchant.id, name="Test Buyer", email="buyer@test.com")
        db_session.add(cust)
        await db_session.flush()

        # 2. Seed 2 Paid Orders (₹2,000 and ₹4,000 -> Total ₹6,000, AOV ₹3,000)
        o1 = Order(
            merchant_id=merchant.id, customer_id=cust.id,
            order_number="FM-REV-01", status="paid",
            subtotal=Decimal("2000.00"), total=Decimal("2000.00"), currency="INR"
        )
        o2 = Order(
            merchant_id=merchant.id, customer_id=cust.id,
            order_number="FM-REV-02", status="paid",
            subtotal=Decimal("4000.00"), total=Decimal("4000.00"), currency="INR"
        )
        db_session.add_all([o1, o2])

        # 3. Seed 1 Abandoned Cart (Value ₹3,500)
        prod = Product(
            merchant_id=merchant.id, name="Pro Headset", slug="pro-headset",
            sku="HD-01", price=Decimal("3500.00"), status="active"
        )
        db_session.add(prod)
        await db_session.flush()

        cart = Cart(merchant_id=merchant.id, customer_id=cust.id, status="active")
        db_session.add(cart)
        await db_session.flush()

        c_item = CartItem(
            cart_id=cart.id, product_id=prod.id,
            quantity=1, unit_price=Decimal("3500.00")
        )
        db_session.add(c_item)

        # 4. Seed 1 Failed Payment (₹1,500)
        pay_failed = Payment(
            merchant_id=merchant.id, order_id=o1.id, amount=Decimal("1500.00"),
            currency="INR", status="failed", provider="razorpay",
            failure_reason="Card declined", idempotency_key="pay_fail_01",
        )
        db_session.add(pay_failed)
        await db_session.commit()

        # Execute Revenue Intelligence
        metrics = await RevenueIntelligenceService.get_overview_metrics(db_session, merchant_id=merchant.id)

        assert metrics["total_revenue"] == 6000.0
        assert metrics["paid_orders"] == 2
        assert metrics["average_order_value"] == 3000.0
        assert metrics["abandoned_cart_count"] == 1
        assert metrics["abandoned_cart_value"] == 3500.0
        assert metrics["failed_payment_count"] == 1
        assert metrics["failed_payment_value"] == 1500.0
        assert metrics["revenue_at_risk"] == 5000.0  # 3500 + 1500
        assert metrics["payment_failure_rate"] == 100.0

    @pytest.mark.asyncio
    async def test_opportunity_engine_detects_abandoned_cart_and_payment_failure(
        self, db_session: AsyncSession, merchant: Merchant
    ):
        cust = Customer(merchant_id=merchant.id, name="Cart Dropper", email="dropper@test.com")
        db_session.add(cust)
        await db_session.flush()

        prod = Product(
            merchant_id=merchant.id, name="Mechanical Keyboard", slug="mech-keyboard",
            sku="KEY-MECH", price=Decimal("4500.00"), status="active"
        )
        db_session.add(prod)
        await db_session.flush()

        # Seed abandoned cart
        cart = Cart(merchant_id=merchant.id, customer_id=cust.id, status="active")
        db_session.add(cart)
        await db_session.flush()
        db_session.add(CartItem(
            cart_id=cart.id, product_id=prod.id,
            quantity=2, unit_price=Decimal("4500.00")
        ))

        # Seed failed payment
        order = Order(
            merchant_id=merchant.id, customer_id=cust.id,
            order_number="FM-FAIL-01", status="pending",
            subtotal=Decimal("9000.00"), total=Decimal("9000.00"), currency="INR"
        )
        db_session.add(order)
        await db_session.flush()

        db_session.add(Payment(
            merchant_id=merchant.id, order_id=order.id, amount=Decimal("9000.00"),
            currency="INR", status="failed", provider="razorpay",
            failure_reason="GATEWAY_TIMEOUT", idempotency_key="pay_fail_02",
        ))
        await db_session.commit()

        # Run Detectors
        opps = await OpportunityEngine.detect_all_opportunities(db_session, merchant_id=merchant.id)

        opp_types = {o.type for o in opps}
        assert OpportunityType.ABANDONED_CART.value in opp_types
        assert OpportunityType.PAYMENT_FAILURE.value in opp_types

        # Verify inspectable evidence
        cart_opp = next(o for o in opps if o.type == OpportunityType.ABANDONED_CART.value)
        assert cart_opp.estimated_value == Decimal("9000.00")
        assert cart_opp.evidence_json["metric"] == "abandoned_cart_value"
        assert cart_opp.evidence_json["cart_count"] == 1
        assert str(cart.id) in cart_opp.affected_entity_ids

        pay_opp = next(o for o in opps if o.type == OpportunityType.PAYMENT_FAILURE.value)
        assert pay_opp.estimated_value == Decimal("9000.00")
        assert pay_opp.evidence_json["metric"] == "failed_payment_value"

    @pytest.mark.asyncio
    async def test_cross_sell_detection(
        self, db_session: AsyncSession, merchant: Merchant
    ):
        cust = Customer(merchant_id=merchant.id, name="Loyal Buyer", email="loyal@test.com")
        db_session.add(cust)
        await db_session.flush()

        p1 = Product(merchant_id=merchant.id, name="Laptop Stand", slug="laptop-stand", sku="STAND-01", price=Decimal("1200.00"), status="active")
        p2 = Product(merchant_id=merchant.id, name="USB-C Hub", slug="usb-c-hub", sku="HUB-01", price=Decimal("2500.00"), status="active")
        db_session.add_all([p1, p2])
        await db_session.flush()

        # Create multi-item orders where p1 and p2 were bought together
        for i in range(3):
            ord_i = Order(
                merchant_id=merchant.id, customer_id=cust.id,
                order_number=f"FM-BUNDLE-{i}", status="paid",
                subtotal=Decimal("3700.00"), total=Decimal("3700.00"), currency="INR"
            )
            db_session.add(ord_i)
            await db_session.flush()
            db_session.add(OrderItem(
                order_id=ord_i.id, product_id=p1.id, product_name="Laptop Stand",
                product_sku="STAND-01", quantity=1, unit_price=Decimal("1200.00"), total=Decimal("1200.00")
            ))
            db_session.add(OrderItem(
                order_id=ord_i.id, product_id=p2.id, product_name="USB-C Hub",
                product_sku="HUB-01", quantity=1, unit_price=Decimal("2500.00"), total=Decimal("2500.00")
            ))
        await db_session.commit()

        opps = await OpportunityEngine.detect_all_opportunities(db_session, merchant_id=merchant.id)
        cross_opp = next((o for o in opps if o.type == OpportunityType.CROSS_SELL.value), None)

        assert cross_opp is not None
        assert "Laptop Stand" in cross_opp.title or "USB-C Hub" in cross_opp.title
        assert cross_opp.evidence_json["co_occurrence_count"] >= 3

    @pytest.mark.asyncio
    async def test_what_if_simulation_deterministic_arithmetic(
        self, db_session: AsyncSession, merchant: Merchant
    ):
        cust = Customer(merchant_id=merchant.id, name="Sim Buyer", email="sim@test.com")
        db_session.add(cust)
        await db_session.flush()

        prod = Product(merchant_id=merchant.id, name="Tablet", slug="tablet-x", sku="TAB-01", price=Decimal("20000.00"), status="active")
        db_session.add(prod)
        await db_session.flush()

        # Seed 10 carts with ₹20,000 each -> Total ₹200,000
        for i in range(10):
            c = Cart(merchant_id=merchant.id, customer_id=cust.id, status="active")
            db_session.add(c)
            await db_session.flush()
            db_session.add(CartItem(
                cart_id=c.id, product_id=prod.id,
                quantity=1, unit_price=Decimal("20000.00")
            ))
        await db_session.commit()

        # Run Simulation: 10% discount on carts >= ₹15,000 with 20% conversion rate
        sim_res = await WhatIfSimulationService.simulate_cart_recovery(
            db=db_session,
            merchant_id=merchant.id,
            discount_percent=10.0,
            min_cart_value=15000.0,
            assumed_conversion_rate=0.20,
        )

        res = sim_res["results"]
        assert res["eligible_cart_count"] == 10
        assert res["current_at_risk_value"] == 200000.0
        # 10 * 0.20 = 2 projected conversions
        assert res["projected_conversions"] == 2
        # Gross = 2 * 20,000 = 40,000
        assert res["gross_recovered_revenue"] == 40000.0
        # Discount = 10% of 40,000 = 4,000
        assert res["discount_cost"] == 4000.0
        # Net = 40,000 - 4,000 = 36,000
        # Margin impact: (40,000 * 0.65) - 4,000 = 26,000 - 4,000 = 22,000.0
        assert res["projected_margin_impact"] == 22000.0
        assert "SIMULATION / ESTIMATE" in res["disclaimer"]
        assert sim_res["simulation_id"] is not None
