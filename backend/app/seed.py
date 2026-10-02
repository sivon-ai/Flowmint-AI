"""
Seed data script for Flowmint AI development.

Creates a realistic demo merchant with products, customers, carts, and orders.
Run: python -m app.seed
"""

import asyncio
import uuid
from decimal import Decimal
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory, engine, Base
from app.core.security import hash_password
from app.models.merchant import Merchant
from app.models.user import User
from app.models.category import Category
from app.models.product import Product, ProductAttribute
from app.models.inventory import Inventory
from app.models.customer import Customer
from app.models.cart import Cart, CartItem
from app.models.order import Order, OrderItem


async def seed():
    """Seed the database with demo data."""
    async with async_session_factory() as db:
        # Check if already seeded
        from sqlalchemy import select
        existing = await db.execute(select(Merchant).where(Merchant.slug == "techmart-india"))
        if existing.scalar_one_or_none():
            print("Database already seeded. Skipping.")
            return

        print("Seeding database...")

        # --- Merchant ---
        merchant = Merchant(
            name="TechMart India",
            slug="techmart-india",
            email="admin@techmart.in",
            phone="+919876543210",
            description="India's premium electronics marketplace",
            status="active",
            settings={
                "currency": "INR",
                "max_discount_percent": 15,
                "recovery_enabled": True,
            },
        )
        db.add(merchant)
        await db.flush()

        # --- User ---
        user = User(
            merchant_id=merchant.id,
            email="admin@techmart.in",
            hashed_password=hash_password("admin123"),
            full_name="Rajesh Kumar",
            role="owner",
            is_active=True,
        )
        db.add(user)

        # --- Categories ---
        laptops = Category(merchant_id=merchant.id, name="Laptops", slug="laptops", sort_order=1)
        phones = Category(merchant_id=merchant.id, name="Smartphones", slug="smartphones", sort_order=2)
        accessories = Category(merchant_id=merchant.id, name="Accessories", slug="accessories", sort_order=3)
        audio = Category(merchant_id=merchant.id, name="Audio", slug="audio", sort_order=4)
        db.add_all([laptops, phones, accessories, audio])
        await db.flush()

        # --- Products ---
        products_data = [
            {
                "name": "ProBook 450 G10", "slug": "probook-450-g10", "sku": "LAP-001",
                "description": "Professional laptop with Intel Core i7, 16GB RAM, 512GB SSD. Perfect for development and business use.",
                "price": Decimal("64999.00"), "compare_at_price": Decimal("74999.00"),
                "category": laptops, "stock": 45,
                "attrs": {"Processor": "Intel Core i7-1355U", "RAM": "16GB DDR4", "Storage": "512GB NVMe SSD", "Display": "15.6\" FHD IPS"},
            },
            {
                "name": "ThinkPad X1 Carbon Gen 11", "slug": "thinkpad-x1-carbon", "sku": "LAP-002",
                "description": "Ultra-light business laptop with 14\" 2.8K OLED display, Intel Core i7, 32GB RAM.",
                "price": Decimal("149999.00"), "compare_at_price": Decimal("169999.00"),
                "category": laptops, "stock": 12,
                "attrs": {"Processor": "Intel Core i7-1365P", "RAM": "32GB LPDDR5", "Storage": "1TB NVMe SSD", "Display": "14\" 2.8K OLED"},
            },
            {
                "name": "IdeaPad Slim 5", "slug": "ideapad-slim-5", "sku": "LAP-003",
                "description": "Affordable performance laptop with AMD Ryzen 5, ideal for students.",
                "price": Decimal("44999.00"), "compare_at_price": Decimal("52999.00"),
                "category": laptops, "stock": 78,
                "attrs": {"Processor": "AMD Ryzen 5 7530U", "RAM": "8GB DDR4", "Storage": "512GB SSD", "Display": "15.6\" FHD IPS"},
            },
            {
                "name": "Galaxy S24 Ultra", "slug": "galaxy-s24-ultra", "sku": "PHN-001",
                "description": "Samsung flagship with S Pen, 200MP camera, Snapdragon 8 Gen 3.",
                "price": Decimal("129999.00"), "compare_at_price": Decimal("134999.00"),
                "category": phones, "stock": 30,
                "attrs": {"Processor": "Snapdragon 8 Gen 3", "RAM": "12GB", "Storage": "256GB", "Camera": "200MP"},
            },
            {
                "name": "iPhone 15 Pro", "slug": "iphone-15-pro", "sku": "PHN-002",
                "description": "Apple's pro smartphone with A17 Pro chip and titanium design.",
                "price": Decimal("134900.00"),
                "category": phones, "stock": 25,
                "attrs": {"Processor": "A17 Pro", "RAM": "8GB", "Storage": "256GB", "Camera": "48MP"},
            },
            {
                "name": "Pixel 8 Pro", "slug": "pixel-8-pro", "sku": "PHN-003",
                "description": "Google's AI-powered smartphone with Tensor G3 and best-in-class camera.",
                "price": Decimal("89999.00"), "compare_at_price": Decimal("106999.00"),
                "category": phones, "stock": 40,
                "attrs": {"Processor": "Google Tensor G3", "RAM": "12GB", "Storage": "128GB", "Camera": "50MP"},
            },
            {
                "name": "MX Master 3S", "slug": "mx-master-3s", "sku": "ACC-001",
                "description": "Logitech's flagship wireless mouse with MagSpeed scroll.",
                "price": Decimal("8995.00"),
                "category": accessories, "stock": 150,
                "attrs": {"Connectivity": "Bluetooth + USB", "Battery": "Rechargeable", "DPI": "8000"},
            },
            {
                "name": "Keychron K8 Pro", "slug": "keychron-k8-pro", "sku": "ACC-002",
                "description": "Wireless mechanical keyboard with QMK/VIA support, hot-swappable.",
                "price": Decimal("7499.00"), "compare_at_price": Decimal("8999.00"),
                "category": accessories, "stock": 60,
                "attrs": {"Layout": "TKL 87-key", "Switch": "Gateron Brown", "Connectivity": "Bluetooth + USB-C"},
            },
            {
                "name": "Sony WH-1000XM5", "slug": "sony-wh-1000xm5", "sku": "AUD-001",
                "description": "Industry-leading noise cancelling wireless headphones.",
                "price": Decimal("26990.00"), "compare_at_price": Decimal("29990.00"),
                "category": audio, "stock": 35,
                "attrs": {"Driver": "30mm", "ANC": "Yes", "Battery": "30 hours", "Connectivity": "Bluetooth 5.2"},
            },
            {
                "name": "AirPods Pro 2", "slug": "airpods-pro-2", "sku": "AUD-002",
                "description": "Apple's premium earbuds with adaptive transparency and USB-C.",
                "price": Decimal("24900.00"),
                "category": audio, "stock": 55,
                "attrs": {"Driver": "Custom Apple", "ANC": "Adaptive", "Battery": "6 hours", "Connectivity": "Bluetooth 5.3"},
            },
        ]

        created_products = []
        for pd in products_data:
            p = Product(
                merchant_id=merchant.id,
                category_id=pd["category"].id,
                name=pd["name"],
                slug=pd["slug"],
                description=pd["description"],
                sku=pd["sku"],
                price=pd["price"],
                compare_at_price=pd.get("compare_at_price"),
                status="active",
            )
            db.add(p)
            await db.flush()

            inv = Inventory(
                product_id=p.id,
                merchant_id=merchant.id,
                quantity=pd["stock"],
                reserved=0,
            )
            db.add(inv)

            for k, v in pd["attrs"].items():
                db.add(ProductAttribute(product_id=p.id, key=k, value=v))

            created_products.append(p)

        # --- Customers ---
        customers_data = [
            {"email": "priya.sharma@gmail.com", "name": "Priya Sharma", "phone": "+919812345678"},
            {"email": "amit.patel@outlook.com", "name": "Amit Patel", "phone": "+919823456789"},
            {"email": "sneha.reddy@yahoo.com", "name": "Sneha Reddy", "phone": "+919834567890"},
            {"email": "rahul.gupta@gmail.com", "name": "Rahul Gupta", "phone": "+919845678901"},
            {"email": "ananya.krishnan@proton.me", "name": "Ananya Krishnan", "phone": "+919856789012"},
        ]

        created_customers = []
        for cd in customers_data:
            c = Customer(
                merchant_id=merchant.id,
                email=cd["email"],
                name=cd["name"],
                phone=cd["phone"],
            )
            db.add(c)
            created_customers.append(c)

        # --- Merchant Policy (Phase 3 & 4) ---
        from app.models.governance import MerchantPolicy
        from app.models.opportunity import Opportunity, OpportunityStatus, OpportunityType

        policy = MerchantPolicy(
            merchant_id=merchant.id,
            max_discount_percentage=Decimal("15.00"),
            max_campaign_budget=Decimal("50000.00"),
            high_value_threshold=Decimal("10000.00"),
            contact_cooldown_hours=24,
            require_approval_all_actions=True,
            auto_approval_max_risk="low",
            allowed_action_types=[
                "abandoned_cart_recovery",
                "cross_sell_bundle",
                "promotional_offer",
                "payment_retry_nudge",
            ],
            is_active=True,
        )
        db.add(policy)

        # --- 37 Abandoned Carts (Total: ₹1,42,000) ---
        cart_values = [3500, 4200, 2800, 5100, 1900, 6200, 3100, 4800, 3900, 2400]
        abandoned_cart_ids = []
        target_p = created_products[0]  # First product
        for i in range(37):
            c = Cart(
                merchant_id=merchant.id,
                customer_id=created_customers[i % len(created_customers)].id,
                status="abandoned",
                created_at=datetime.now(timezone.utc),
            )
            db.add(c)
            await db.flush()
            abandoned_cart_ids.append(str(c.id))

            val = cart_values[i % len(cart_values)]
            item = CartItem(
                cart_id=c.id,
                product_id=target_p.id,
                quantity=1,
                unit_price=Decimal(str(val)),
            )
            db.add(item)

        # --- Canonical Opportunity 1: ₹1,42,000 At-Risk Cart Abandonment ---
        opp_abandoned = Opportunity(
            merchant_id=merchant.id,
            type=OpportunityType.ABANDONED_CART.value,
            title="High Checkout Abandonment (₹1,42,000 at risk)",
            description="37 high-intent buyer carts were abandoned during checkout in the last 24 hours.",
            status=OpportunityStatus.DETECTED.value,
            priority="high",
            estimated_value=Decimal("142000.00"),
            confidence=Decimal("0.92"),
            evidence_json={
                "metric": "cart_abandonment_spike",
                "eligible_carts": 37,
                "at_risk_amount": 142000.0,
                "time_window": "last_24h",
                "cart_ids": abandoned_cart_ids[:10],
                "rationale": "Abandonment rate increased by 18% over the 7-day rolling baseline.",
            },
            recommended_action="abandoned_cart_recovery",
            affected_entity_type="cart",
            affected_entity_ids=abandoned_cart_ids[:5],
        )
        db.add(opp_abandoned)

        # --- Canonical Opportunity 2: Cross-sell Opportunity ---
        opp_cross_sell = Opportunity(
            merchant_id=merchant.id,
            type=OpportunityType.CROSS_SELL.value,
            title="Cross-Sell Bundle: MacBook Air + USB-C Hub Affinity",
            description="Buyers of laptops have an 34% affinity for multi-port USB-C hubs when bundled with a 10% discount.",
            status=OpportunityStatus.DETECTED.value,
            priority="medium",
            estimated_value=Decimal("34500.00"),
            confidence=Decimal("0.85"),
            evidence_json={
                "metric": "high_co_purchase_affinity",
                "primary_product": "MacBook Air M2",
                "companion_product": "Anker 7-in-1 USB-C Hub",
                "co_occurrence_count": 28,
                "estimated_monthly_lift": 34500.0,
            },
            recommended_action="cross_sell_bundle",
            affected_entity_type="product",
            affected_entity_ids=[str(created_products[0].id)],
        )
        db.add(opp_cross_sell)

        await db.commit()
        print(f"✓ Seeded merchant: {merchant.name}")
        print(f"✓ Seeded {len(created_products)} products across 4 categories")
        print(f"✓ Seeded {len(created_customers)} customers")
        print(f"✓ Seeded 37 abandoned carts totaling ₹1,42,000")
        print(f"✓ Seeded 2 canonical revenue opportunities with inspectable evidence")
        print(f"✓ Seeded MerchantPolicy (max 15% discount, 50k budget)")
        print(f"\n  Login: admin@techmart.in / admin123")


if __name__ == "__main__":
    asyncio.run(seed())
