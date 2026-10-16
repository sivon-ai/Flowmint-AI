"""
Store Synchronization Service — Shopify, WooCommerce, and Custom Store.

Handles:
- OAuth flow & token exchange for Shopify.
- REST API verification & sync for WooCommerce.
- Ingestion API & Webhook contract for Custom Store.
- Multi-tenant isolation and strict idempotency using StoreEntityMapping.
- Synchronizing Products, Inventory, Customers, Orders, and financial totals.
- Safe disconnect without deleting historical business records.
"""

import hmac
import hashlib
import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.encryption import decrypt_credentials, encrypt_credentials
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.ssrf import validate_outbound_url
from app.models.category import Category
from app.models.customer import Customer
from app.models.inventory import Inventory
from app.models.merchant import Merchant
from app.models.order import Order, OrderItem
from app.models.product import Product
from app.models.store_connection import StoreConnection, StoreEntityMapping, StoreSyncJob
from app.schemas.store import (
    CustomIngestCustomerItem,
    CustomIngestOrderItem,
    CustomIngestProductItem,
    CustomIngestResult,
    CustomStoreConnectRequest,
    CustomStoreConnectResponse,
    ShopifyAuthInitRequest,
    ShopifyAuthInitResponse,
    StoreConnectionResponse,
    StoreSyncStatusResponse,
    WooCommerceConnectRequest,
)

logger = logging.getLogger(__name__)
settings = get_settings()


def _slugify(text: str) -> str:
    import re
    s = text.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s or "item"


class StoreSyncService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ==========================================
    # 1. SHOPIFY OAUTH & CONNECTION
    # ==========================================

    async def initiate_shopify_oauth(
        self, merchant_id: uuid.UUID, data: ShopifyAuthInitRequest
    ) -> ShopifyAuthInitResponse:
        """
        Validate shop domain and return Shopify OAuth authorization URL.
        If Shopify app credentials are not configured, returns configured=False.
        """
        raw_shop = data.shop_domain.strip().lower()
        if not raw_shop.endswith(".myshopify.com"):
            raw_shop = f"{raw_shop}.myshopify.com"

        # Validate domain format
        import re
        if not re.match(r"^[a-zA-Z0-9][a-zA-Z0-9\-]*\.myshopify\.com$", raw_shop):
            raise ValidationError("Invalid Shopify store domain format. Expected: your-store.myshopify.com")

        if not settings.shopify_client_id or not settings.shopify_client_secret:
            return ShopifyAuthInitResponse(
                configured=False,
                message=(
                    "Shopify App credentials (SHOPIFY_CLIENT_ID / SHOPIFY_CLIENT_SECRET) are not configured. "
                    "Please configure them in your server environment to enable live Shopify OAuth."
                ),
            )

        # Generate secure CSRF state containing merchant_id
        nonce = uuid.uuid4().hex
        state = f"{merchant_id}:{nonce}"

        scopes = "read_products,read_orders,read_inventory,read_customers"
        redirect_uri = settings.shopify_redirect_uri or f"{settings.backend_public_url}/api/v1/stores/shopify/callback"

        auth_url = (
            f"https://{raw_shop}/admin/oauth/authorize?"
            f"client_id={settings.shopify_client_id}&"
            f"scope={scopes}&"
            f"redirect_uri={redirect_uri}&"
            f"state={state}"
        )

        return ShopifyAuthInitResponse(
            authorization_url=auth_url,
            state=state,
            configured=True,
            message="Redirect merchant to authorization_url",
        )

    async def handle_shopify_callback(
        self, code: str, shop: str, state: str, hmac_str: str, query_params: dict[str, Any]
    ) -> StoreConnection:
        """
        Validate HMAC, exchange auth code for access token, and persist StoreConnection.
        """
        if not settings.shopify_client_secret:
            raise ValidationError("Shopify client secret not configured on server")

        # 1. Verify HMAC
        params_to_verify = {k: v for k, v in query_params.items() if k not in ("hmac", "signature")}
        sorted_params = "&".join(f"{k}={params_to_verify[k]}" for k in sorted(params_to_verify.keys()))
        calculated_hmac = hmac.new(
            settings.shopify_client_secret.encode("utf-8"),
            sorted_params.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(calculated_hmac, hmac_str):
            raise ValidationError("Invalid Shopify OAuth HMAC signature")

        # 2. Extract merchant_id from state
        try:
            merchant_id_str, _ = state.split(":", 1)
            merchant_id = uuid.UUID(merchant_id_str)
        except Exception:
            raise ValidationError("Invalid OAuth state token")

        # 3. Exchange code for access token
        token_url = f"https://{shop}/admin/oauth/access_token"
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                token_url,
                json={
                    "client_id": settings.shopify_client_id,
                    "client_secret": settings.shopify_client_secret,
                    "code": code,
                },
            )
            if resp.status_code != 200:
                logger.error("Shopify token exchange failed: %s %s", resp.status_code, resp.text)
                raise ValidationError(f"Failed to exchange Shopify authorization code: {resp.text}")
            token_data = resp.json()

        access_token = token_data.get("access_token")
        if not access_token:
            raise ValidationError("No access token returned by Shopify")

        # 4. Save connection with encrypted credentials
        encrypted = encrypt_credentials({"access_token": access_token, "shop": shop})
        scopes = token_data.get("scope", "read_products,read_orders,read_inventory,read_customers")

        # Check existing connection
        stmt = select(StoreConnection).where(
            StoreConnection.merchant_id == merchant_id,
            StoreConnection.provider == "shopify",
        )
        existing = (await self.db.execute(stmt)).scalar_one_or_none()

        if existing:
            existing.store_url = f"https://{shop}"
            existing.store_name = shop.replace(".myshopify.com", "")
            existing.status = "connected"
            existing.scopes = scopes
            existing.encrypted_credentials = encrypted
            existing.disconnected_at = None
            connection = existing
        else:
            connection = StoreConnection(
                merchant_id=merchant_id,
                provider="shopify",
                store_url=f"https://{shop}",
                store_name=shop.replace(".myshopify.com", ""),
                external_store_id=shop,
                status="connected",
                scopes=scopes,
                encrypted_credentials=encrypted,
            )
            self.db.add(connection)

        # Update merchant onboarding state in settings
        await self._mark_merchant_onboarding(merchant_id, store_mode="shopify")

        await self.db.commit()
        await self.db.refresh(connection)

        # Trigger initial sync in background
        await self.sync_shopify_store(connection)
        return connection

    # ==========================================
    # 2. WOOCOMMERCE REST API CONNECTION
    # ==========================================

    async def connect_woocommerce(
        self, merchant_id: uuid.UUID, data: WooCommerceConnectRequest
    ) -> StoreConnection:
        """
        Validate store URL (with SSRF protection), test credentials, and save connection.
        """
        # 1. SSRF Defense
        clean_url = validate_outbound_url(data.store_url)

        # 2. Verify credentials with minimal authenticated request
        test_endpoint = f"{clean_url}/wp-json/wc/v3/system_status"
        fallback_endpoint = f"{clean_url}/wp-json/wc/v3/products?per_page=1"

        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            try:
                resp = await client.get(
                    test_endpoint,
                    auth=(data.consumer_key, data.consumer_secret),
                )
                if resp.status_code in (401, 403):
                    raise ValidationError(
                        "WooCommerce authentication failed: Invalid Consumer Key or Consumer Secret."
                    )
                if resp.status_code != 200:
                    # Fallback to products endpoint check
                    resp2 = await client.get(
                        fallback_endpoint,
                        auth=(data.consumer_key, data.consumer_secret),
                    )
                    if resp2.status_code in (401, 403):
                        raise ValidationError(
                            "WooCommerce authentication failed: Invalid Consumer Key or Consumer Secret."
                        )
                    if resp2.status_code != 200:
                        raise ValidationError(
                            f"WooCommerce API returned HTTP {resp.status_code}. Please ensure WooCommerce REST API is enabled."
                        )
            except httpx.RequestError as e:
                logger.error("WooCommerce connection test error: %s", str(e))
                raise ValidationError(
                    f"Could not connect to WooCommerce store at {clean_url}. Error: {str(e)}"
                )

        # 3. Encrypt credentials and persist
        encrypted = encrypt_credentials({
            "consumer_key": data.consumer_key,
            "consumer_secret": data.consumer_secret,
            "store_url": clean_url,
        })

        stmt = select(StoreConnection).where(
            StoreConnection.merchant_id == merchant_id,
            StoreConnection.provider == "woocommerce",
        )
        existing = (await self.db.execute(stmt)).scalar_one_or_none()

        store_name = data.store_name or clean_url.replace("https://", "").replace("http://", "").split("/")[0]

        if existing:
            existing.store_url = clean_url
            existing.store_name = store_name
            existing.status = "connected"
            existing.scopes = "read"
            existing.encrypted_credentials = encrypted
            existing.disconnected_at = None
            connection = existing
        else:
            connection = StoreConnection(
                merchant_id=merchant_id,
                provider="woocommerce",
                store_url=clean_url,
                store_name=store_name,
                status="connected",
                scopes="read",
                encrypted_credentials=encrypted,
            )
            self.db.add(connection)

        # Update merchant onboarding
        await self._mark_merchant_onboarding(merchant_id, store_mode="woocommerce")

        await self.db.commit()
        await self.db.refresh(connection)

        # Initial synchronization
        await self.sync_woocommerce_store(connection)
        return connection

    # ==========================================
    # 3. CUSTOM STORE INGESTION API
    # ==========================================

    async def connect_custom_store(
        self, merchant_id: uuid.UUID, data: CustomStoreConnectRequest
    ) -> CustomStoreConnectResponse:
        """
        Generate API ingestion credentials and endpoints for custom React/Node/Python storefronts.
        """
        clean_url = data.store_url.strip()
        if not clean_url.startswith(("http://", "https://")):
            clean_url = "https://" + clean_url

        ingest_api_key = f"flw_live_{uuid.uuid4().hex}"
        encrypted = encrypt_credentials({
            "api_key": ingest_api_key,
            "store_name": data.store_name,
            "store_url": clean_url,
        })

        stmt = select(StoreConnection).where(
            StoreConnection.merchant_id == merchant_id,
            StoreConnection.provider == "custom",
        )
        existing = (await self.db.execute(stmt)).scalar_one_or_none()

        if existing:
            existing.store_url = clean_url
            existing.store_name = data.store_name
            existing.status = "connected"
            existing.scopes = "ingest_products,ingest_orders,ingest_customers"
            existing.encrypted_credentials = encrypted
            existing.disconnected_at = None
            connection = existing
        else:
            connection = StoreConnection(
                merchant_id=merchant_id,
                provider="custom",
                store_url=clean_url,
                store_name=data.store_name,
                status="connected",
                scopes="ingest_products,ingest_orders,ingest_customers",
                encrypted_credentials=encrypted,
            )
            self.db.add(connection)

        # Update merchant onboarding
        await self._mark_merchant_onboarding(merchant_id, store_mode="custom")

        await self.db.commit()
        await self.db.refresh(connection)

        base_endpoint = f"{settings.backend_public_url}/api/v1/stores/custom"

        return CustomStoreConnectResponse(
            connection=StoreConnectionResponse.model_validate(connection),
            ingestion_api_key=ingest_api_key,
            ingestion_endpoint=base_endpoint,
            documentation={
                "overview": "Send JSON payloads to ingest products, customers, and orders from your custom storefront.",
                "auth_header": f"X-Flowmint-Store-Key: {ingest_api_key}",
                "endpoints": {
                    "ingest_products": f"{base_endpoint}/ingest/products",
                    "ingest_customers": f"{base_endpoint}/ingest/customers",
                    "ingest_orders": f"{base_endpoint}/ingest/orders",
                },
                "status": "ready",
            },
        )

    # ==========================================
    # 4. CUSTOM STORE INGESTION EXECUTION
    # ==========================================

    async def ingest_products(
        self, merchant_id: uuid.UUID, connection_id: uuid.UUID, items: list[CustomIngestProductItem]
    ) -> CustomIngestResult:
        processed = 0
        failed = 0
        errors = []

        for item in items:
            try:
                await self._upsert_product(
                    merchant_id=merchant_id,
                    connection_id=connection_id,
                    external_id=item.external_id,
                    name=item.name,
                    sku=item.sku,
                    price=item.price,
                    compare_at_price=item.compare_at_price,
                    currency=item.currency,
                    description=item.description,
                    quantity=item.quantity,
                    status=item.status,
                )
                processed += 1
            except Exception as e:
                failed += 1
                errors.append(f"Product '{item.name}' ({item.sku}): {str(e)}")

        await self._update_connection_sync_summary(connection_id, products_delta=processed)
        await self.db.commit()

        return CustomIngestResult(
            entity_type="products",
            records_processed=processed,
            records_failed=failed,
            errors=errors[:10],
        )

    async def ingest_customers(
        self, merchant_id: uuid.UUID, connection_id: uuid.UUID, items: list[CustomIngestCustomerItem]
    ) -> CustomIngestResult:
        processed = 0
        failed = 0
        errors = []

        for item in items:
            try:
                await self._upsert_customer(
                    merchant_id=merchant_id,
                    connection_id=connection_id,
                    external_id=item.external_id,
                    email=item.email,
                    name=item.name,
                    phone=item.phone,
                )
                processed += 1
            except Exception as e:
                failed += 1
                errors.append(f"Customer '{item.email}': {str(e)}")

        await self._update_connection_sync_summary(connection_id, customers_delta=processed)
        await self.db.commit()

        return CustomIngestResult(
            entity_type="customers",
            records_processed=processed,
            records_failed=failed,
            errors=errors[:10],
        )

    async def ingest_orders(
        self, merchant_id: uuid.UUID, connection_id: uuid.UUID, items: list[CustomIngestOrderItem]
    ) -> CustomIngestResult:
        processed = 0
        failed = 0
        errors = []

        for item in items:
            try:
                await self._upsert_order(
                    merchant_id=merchant_id,
                    connection_id=connection_id,
                    external_id=item.external_id,
                    order_number=item.order_number,
                    customer_email=item.customer_email,
                    customer_name=item.customer_name,
                    total=item.total,
                    currency=item.currency,
                    status=item.status,
                    items_data=item.items,
                )
                processed += 1
            except Exception as e:
                failed += 1
                errors.append(f"Order '{item.order_number}': {str(e)}")

        await self._update_connection_sync_summary(connection_id, orders_delta=processed)
        await self.db.commit()

        return CustomIngestResult(
            entity_type="orders",
            records_processed=processed,
            records_failed=failed,
            errors=errors[:10],
        )

    # ==========================================
    # 5. SYNCHRONIZATION HELPERS (IDEMPOTENT UPSERT)
    # ==========================================

    async def _upsert_product(
        self,
        merchant_id: uuid.UUID,
        connection_id: uuid.UUID,
        external_id: str,
        name: str,
        sku: str,
        price: Decimal,
        compare_at_price: Decimal | None = None,
        currency: str = "INR",
        description: str | None = None,
        quantity: int = 0,
        status: str = "active",
        category_name: str | None = None,
    ) -> Product:
        # Check mapping
        stmt = select(StoreEntityMapping).where(
            StoreEntityMapping.merchant_id == merchant_id,
            StoreEntityMapping.connection_id == connection_id,
            StoreEntityMapping.entity_type == "product",
            StoreEntityMapping.external_id == external_id,
        )
        mapping = (await self.db.execute(stmt)).scalar_one_or_none()

        if mapping:
            # Update existing product
            p_stmt = select(Product).where(Product.id == mapping.internal_id)
            product = (await self.db.execute(p_stmt)).scalar_one_or_none()
            if product:
                product.name = name
                product.price = price
                product.compare_at_price = compare_at_price
                product.description = description
                product.status = status if status in ("active", "draft", "archived") else "active"

                # Update inventory
                inv_stmt = select(Inventory).where(Inventory.product_id == product.id)
                inv = (await self.db.execute(inv_stmt)).scalar_one_or_none()
                if inv:
                    inv.quantity = max(0, quantity)
                return product

        # Resolve category if provided
        category_id = None
        if category_name:
            c_stmt = select(Category).where(
                Category.merchant_id == merchant_id, Category.name == category_name
            )
            cat = (await self.db.execute(c_stmt)).scalar_one_or_none()
            if cat:
                category_id = cat.id

        # Generate unique SKU if conflicted
        base_sku = sku or f"EXT-{external_id[:8]}"
        sku_check = await self.db.execute(
            select(Product.id).where(Product.merchant_id == merchant_id, Product.sku == base_sku)
        )
        if sku_check.scalar_one_or_none():
            base_sku = f"{base_sku}-{uuid.uuid4().hex[:4]}"

        # Generate unique slug
        base_slug = _slugify(name)
        slug_check = await self.db.execute(
            select(Product.id).where(Product.merchant_id == merchant_id, Product.slug == base_slug)
        )
        if slug_check.scalar_one_or_none():
            base_slug = f"{base_slug}-{uuid.uuid4().hex[:4]}"

        product = Product(
            merchant_id=merchant_id,
            category_id=category_id,
            name=name,
            slug=base_slug,
            description=description,
            sku=base_sku,
            price=price,
            compare_at_price=compare_at_price,
            currency=currency or "INR",
            status=status if status in ("active", "draft", "archived") else "active",
        )
        self.db.add(product)
        await self.db.flush()

        # Add Inventory
        inv = Inventory(
            product_id=product.id,
            merchant_id=merchant_id,
            quantity=max(0, quantity),
            reserved=0,
        )
        self.db.add(inv)

        # Record mapping
        new_mapping = StoreEntityMapping(
            merchant_id=merchant_id,
            connection_id=connection_id,
            entity_type="product",
            external_id=external_id,
            internal_id=product.id,
        )
        self.db.add(new_mapping)
        return product

    async def _upsert_customer(
        self,
        merchant_id: uuid.UUID,
        connection_id: uuid.UUID,
        external_id: str,
        email: str,
        name: str,
        phone: str | None = None,
    ) -> Customer:
        # Check mapping
        stmt = select(StoreEntityMapping).where(
            StoreEntityMapping.merchant_id == merchant_id,
            StoreEntityMapping.connection_id == connection_id,
            StoreEntityMapping.entity_type == "customer",
            StoreEntityMapping.external_id == external_id,
        )
        mapping = (await self.db.execute(stmt)).scalar_one_or_none()

        if mapping:
            c_stmt = select(Customer).where(Customer.id == mapping.internal_id)
            customer = (await self.db.execute(c_stmt)).scalar_one_or_none()
            if customer:
                customer.name = name
                customer.phone = phone or customer.phone
                return customer

        # Check existing customer by email under this merchant
        existing_email_stmt = select(Customer).where(
            Customer.merchant_id == merchant_id, Customer.email == email.lower().strip()
        )
        customer = (await self.db.execute(existing_email_stmt)).scalar_one_or_none()

        if not customer:
            customer = Customer(
                merchant_id=merchant_id,
                email=email.lower().strip(),
                name=name or email.split("@")[0],
                phone=phone,
            )
            self.db.add(customer)
            await self.db.flush()

        new_mapping = StoreEntityMapping(
            merchant_id=merchant_id,
            connection_id=connection_id,
            entity_type="customer",
            external_id=external_id,
            internal_id=customer.id,
        )
        self.db.add(new_mapping)
        return customer

    async def _upsert_order(
        self,
        merchant_id: uuid.UUID,
        connection_id: uuid.UUID,
        external_id: str,
        order_number: str,
        customer_email: str,
        customer_name: str,
        total: Decimal,
        currency: str = "INR",
        status: str = "confirmed",
        items_data: list[dict] = None,
    ) -> Order:
        # Check mapping
        stmt = select(StoreEntityMapping).where(
            StoreEntityMapping.merchant_id == merchant_id,
            StoreEntityMapping.connection_id == connection_id,
            StoreEntityMapping.entity_type == "order",
            StoreEntityMapping.external_id == external_id,
        )
        mapping = (await self.db.execute(stmt)).scalar_one_or_none()

        if mapping:
            o_stmt = select(Order).where(Order.id == mapping.internal_id)
            order = (await self.db.execute(o_stmt)).scalar_one_or_none()
            if order:
                order.status = status
                order.total = total
                return order

        # Ensure customer exists
        cust = await self._upsert_customer(
            merchant_id=merchant_id,
            connection_id=connection_id,
            external_id=f"cust_{customer_email}",
            email=customer_email,
            name=customer_name,
        )

        # Unique order number per merchant
        base_order_number = order_number or f"ORD-{external_id[:8]}"
        existing_num = await self.db.execute(
            select(Order.id).where(Order.merchant_id == merchant_id, Order.order_number == base_order_number)
        )
        if existing_num.scalar_one_or_none():
            base_order_number = f"{base_order_number}-{uuid.uuid4().hex[:4]}"

        order = Order(
            merchant_id=merchant_id,
            customer_id=cust.id,
            order_number=base_order_number,
            status=status,
            subtotal=total,
            tax=Decimal("0.00"),
            discount=Decimal("0.00"),
            total=total,
            currency=currency or "INR",
        )
        self.db.add(order)
        await self.db.flush()

        # Add line items if provided
        if items_data:
            for itm in items_data:
                # Find or create placeholder product
                p_name = itm.get("name", "Product Item")
                p_sku = itm.get("sku", f"ITEM-{uuid.uuid4().hex[:6]}")
                p_qty = itm.get("quantity", 1)
                p_price = Decimal(str(itm.get("price", "0.00")))

                prod = await self._upsert_product(
                    merchant_id=merchant_id,
                    connection_id=connection_id,
                    external_id=f"item_{p_sku}",
                    name=p_name,
                    sku=p_sku,
                    price=p_price,
                    currency=currency,
                )

                order_item = OrderItem(
                    order_id=order.id,
                    product_id=prod.id,
                    product_name=p_name,
                    product_sku=p_sku,
                    quantity=p_qty,
                    unit_price=p_price,
                    total=p_price * p_qty,
                )
                self.db.add(order_item)

        new_mapping = StoreEntityMapping(
            merchant_id=merchant_id,
            connection_id=connection_id,
            entity_type="order",
            external_id=external_id,
            internal_id=order.id,
        )
        self.db.add(new_mapping)
        return order

    # ==========================================
    # 6. PROVIDER API DRIVERS
    # ==========================================

    async def sync_shopify_store(self, connection: StoreConnection) -> StoreSyncStatusResponse:
        """Fetch real data from Shopify Admin API and idempotently map into Flowmint."""
        creds = decrypt_credentials(connection.encrypted_credentials)
        access_token = creds.get("access_token")
        shop = creds.get("shop")

        connection.sync_status = "running"
        job = StoreSyncJob(
            merchant_id=connection.merchant_id,
            connection_id=connection.id,
            status="running",
            entity_type="all",
            started_at=datetime.now(timezone.utc),
        )
        self.db.add(job)
        await self.db.commit()

        api_version = settings.shopify_api_version or "2024-01"
        base_url = f"https://{shop}/admin/api/{api_version}"
        headers = {"X-Shopify-Access-Token": access_token}

        products_count = 0
        customers_count = 0
        orders_count = 0

        async with httpx.AsyncClient(timeout=20.0) as client:
            try:
                # 1. Sync Products
                p_res = await client.get(f"{base_url}/products.json?limit=50", headers=headers)
                if p_res.status_code == 200:
                    for p in p_res.json().get("products", []):
                        variants = p.get("variants", [])
                        first_var = variants[0] if variants else {}
                        stock = sum(v.get("inventory_quantity", 0) for v in variants)
                        price = Decimal(str(first_var.get("price", "0.00")))
                        compare_at = Decimal(str(first_var.get("compare_at_price"))) if first_var.get("compare_at_price") else None

                        await self._upsert_product(
                            merchant_id=connection.merchant_id,
                            connection_id=connection.id,
                            external_id=str(p["id"]),
                            name=p.get("title", "Shopify Product"),
                            sku=first_var.get("sku") or f"SHPFY-{p['id']}",
                            price=price,
                            compare_at_price=compare_at,
                            description=p.get("body_html"),
                            quantity=stock,
                            status="active" if p.get("status") == "active" else "draft",
                        )
                        products_count += 1

                # 2. Sync Customers
                c_res = await client.get(f"{base_url}/customers.json?limit=50", headers=headers)
                if c_res.status_code == 200:
                    for c in c_res.json().get("customers", []):
                        if c.get("email"):
                            await self._upsert_customer(
                                merchant_id=connection.merchant_id,
                                connection_id=connection.id,
                                external_id=str(c["id"]),
                                email=c["email"],
                                name=f"{c.get('first_name', '')} {c.get('last_name', '')}".strip() or c["email"],
                                phone=c.get("phone"),
                            )
                            customers_count += 1

                # 3. Sync Orders
                o_res = await client.get(f"{base_url}/orders.json?status=any&limit=50", headers=headers)
                if o_res.status_code == 200:
                    for o in o_res.json().get("orders", []):
                        cust = o.get("customer") or {}
                        c_email = cust.get("email") or o.get("email") or f"customer_{o['id']}@shopify.external"
                        c_name = f"{cust.get('first_name', '')} {cust.get('last_name', '')}".strip() or "Shopify Customer"

                        items_data = [
                            {
                                "name": itm.get("title", "Shopify Item"),
                                "sku": itm.get("sku") or f"ITM-{itm['id']}",
                                "quantity": itm.get("quantity", 1),
                                "price": itm.get("price", "0.00"),
                            }
                            for itm in o.get("line_items", [])
                        ]

                        await self._upsert_order(
                            merchant_id=connection.merchant_id,
                            connection_id=connection.id,
                            external_id=str(o["id"]),
                            order_number=o.get("name") or str(o.get("order_number") or o["id"]),
                            customer_email=c_email,
                            customer_name=c_name,
                            total=Decimal(str(o.get("total_price", "0.00"))),
                            currency=o.get("currency", "INR"),
                            status="completed" if o.get("financial_status") == "paid" else "pending",
                            items_data=items_data,
                        )
                        orders_count += 1

                # Finalize job
                job.status = "completed"
                job.records_processed = products_count + customers_count + orders_count
                job.completed_at = datetime.now(timezone.utc)
                job.summary_json = {
                    "products": products_count,
                    "customers": customers_count,
                    "orders": orders_count,
                }

                connection.sync_status = "completed"
                connection.last_sync_at = datetime.now(timezone.utc)
                connection.sync_summary = job.summary_json
                connection.last_error = None

                await self.db.commit()

            except Exception as e:
                logger.error("Shopify sync failed: %s", str(e), exc_info=True)
                job.status = "failed"
                job.error_message = str(e)
                connection.sync_status = "failed"
                connection.last_error = str(e)
                await self.db.commit()

        return StoreSyncStatusResponse(
            connection_id=connection.id,
            sync_status=connection.sync_status,
            last_sync_at=connection.last_sync_at,
            sync_summary=connection.sync_summary or {},
            records_processed=job.records_processed,
            records_failed=job.records_failed,
            last_error=connection.last_error,
        )

    async def sync_woocommerce_store(self, connection: StoreConnection) -> StoreSyncStatusResponse:
        """Fetch real data from WooCommerce REST API and idempotently map into Flowmint."""
        creds = decrypt_credentials(connection.encrypted_credentials)
        consumer_key = creds.get("consumer_key")
        consumer_secret = creds.get("consumer_secret")
        store_url = creds.get("store_url")

        connection.sync_status = "running"
        job = StoreSyncJob(
            merchant_id=connection.merchant_id,
            connection_id=connection.id,
            status="running",
            entity_type="all",
            started_at=datetime.now(timezone.utc),
        )
        self.db.add(job)
        await self.db.commit()

        products_count = 0
        customers_count = 0
        orders_count = 0

        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            try:
                auth = (consumer_key, consumer_secret)

                # 1. Sync Products
                p_res = await client.get(f"{store_url}/wp-json/wc/v3/products?per_page=50", auth=auth)
                if p_res.status_code == 200:
                    for p in p_res.json():
                        price = Decimal(str(p.get("price") or "0.00"))
                        reg_price = Decimal(str(p.get("regular_price"))) if p.get("regular_price") else None
                        stock = p.get("stock_quantity") or 0

                        await self._upsert_product(
                            merchant_id=connection.merchant_id,
                            connection_id=connection.id,
                            external_id=str(p["id"]),
                            name=p.get("name", "WooCommerce Product"),
                            sku=p.get("sku") or f"WC-{p['id']}",
                            price=price,
                            compare_at_price=reg_price if reg_price and reg_price > price else None,
                            description=p.get("description"),
                            quantity=stock,
                            status="active" if p.get("status") == "publish" else "draft",
                        )
                        products_count += 1

                # 2. Sync Customers
                c_res = await client.get(f"{store_url}/wp-json/wc/v3/customers?per_page=50", auth=auth)
                if c_res.status_code == 200:
                    for c in c_res.json():
                        if c.get("email"):
                            await self._upsert_customer(
                                merchant_id=connection.merchant_id,
                                connection_id=connection.id,
                                external_id=str(c["id"]),
                                email=c["email"],
                                name=f"{c.get('first_name', '')} {c.get('last_name', '')}".strip() or c["email"],
                                phone=c.get("billing", {}).get("phone"),
                            )
                            customers_count += 1

                # 3. Sync Orders
                o_res = await client.get(f"{store_url}/wp-json/wc/v3/orders?per_page=50", auth=auth)
                if o_res.status_code == 200:
                    for o in o_res.json():
                        billing = o.get("billing", {})
                        c_email = billing.get("email") or f"order_{o['id']}@wc.external"
                        c_name = f"{billing.get('first_name', '')} {billing.get('last_name', '')}".strip() or "WC Customer"

                        items_data = [
                            {
                                "name": itm.get("name", "WC Item"),
                                "sku": itm.get("sku") or f"WC-ITM-{itm['id']}",
                                "quantity": itm.get("quantity", 1),
                                "price": itm.get("price", "0.00"),
                            }
                            for itm in o.get("line_items", [])
                        ]

                        wc_status = o.get("status", "processing")
                        mapped_status = "completed" if wc_status in ("completed", "processing") else "pending"
                        if wc_status == "cancelled":
                            mapped_status = "cancelled"

                        await self._upsert_order(
                            merchant_id=connection.merchant_id,
                            connection_id=connection.id,
                            external_id=str(o["id"]),
                            order_number=str(o.get("number") or o["id"]),
                            customer_email=c_email,
                            customer_name=c_name,
                            total=Decimal(str(o.get("total", "0.00"))),
                            currency=o.get("currency", "INR"),
                            status=mapped_status,
                            items_data=items_data,
                        )
                        orders_count += 1

                # Finalize job
                job.status = "completed"
                job.records_processed = products_count + customers_count + orders_count
                job.completed_at = datetime.now(timezone.utc)
                job.summary_json = {
                    "products": products_count,
                    "customers": customers_count,
                    "orders": orders_count,
                }

                connection.sync_status = "completed"
                connection.last_sync_at = datetime.now(timezone.utc)
                connection.sync_summary = job.summary_json
                connection.last_error = None

                await self.db.commit()

            except Exception as e:
                logger.error("WooCommerce sync failed: %s", str(e), exc_info=True)
                job.status = "failed"
                job.error_message = str(e)
                connection.sync_status = "failed"
                connection.last_error = str(e)
                await self.db.commit()

        return StoreSyncStatusResponse(
            connection_id=connection.id,
            sync_status=connection.sync_status,
            last_sync_at=connection.last_sync_at,
            sync_summary=connection.sync_summary or {},
            records_processed=job.records_processed,
            records_failed=job.records_failed,
            last_error=connection.last_error,
        )

    # ==========================================
    # 7. CONNECTION MANAGEMENT & ONBOARDING
    # ==========================================

    async def get_connections(self, merchant_id: uuid.UUID) -> list[StoreConnectionResponse]:
        """List active store connections for the authenticated merchant."""
        stmt = (
            select(StoreConnection)
            .where(
                StoreConnection.merchant_id == merchant_id,
                StoreConnection.status != "disconnected",
            )
            .order_by(StoreConnection.created_at.desc())
        )
        result = await self.db.execute(stmt)
        return [StoreConnectionResponse.model_validate(c) for c in result.scalars().all()]

    async def get_connection(self, merchant_id: uuid.UUID, connection_id: uuid.UUID) -> StoreConnection:
        stmt = select(StoreConnection).where(
            StoreConnection.id == connection_id,
            StoreConnection.merchant_id == merchant_id,
        )
        conn = (await self.db.execute(stmt)).scalar_one_or_none()
        if not conn:
            raise NotFoundError("StoreConnection", str(connection_id))
        return conn

    async def disconnect(self, merchant_id: uuid.UUID, connection_id: uuid.UUID) -> StoreConnectionResponse:
        conn = await self.get_connection(merchant_id, connection_id)
        conn.status = "disconnected"
        conn.disconnected_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(conn)
        return StoreConnectionResponse.model_validate(conn)

    async def trigger_sync(self, merchant_id: uuid.UUID, connection_id: uuid.UUID) -> StoreSyncStatusResponse:
        conn = await self.get_connection(merchant_id, connection_id)
        if conn.status == "disconnected":
            raise ValidationError("Cannot synchronize a disconnected store.")

        if conn.provider == "shopify":
            return await self.sync_shopify_store(conn)
        elif conn.provider == "woocommerce":
            return await self.sync_woocommerce_store(conn)
        else:
            # Custom store
            conn.last_sync_at = datetime.now(timezone.utc)
            conn.sync_status = "completed"
            await self.db.commit()
            return StoreSyncStatusResponse(
                connection_id=conn.id,
                sync_status="completed",
                last_sync_at=conn.last_sync_at,
                sync_summary=conn.sync_summary or {},
                records_processed=0,
                records_failed=0,
            )

    async def _update_connection_sync_summary(
        self, connection_id: uuid.UUID, products_delta: int = 0, customers_delta: int = 0, orders_delta: int = 0
    ):
        stmt = select(StoreConnection).where(StoreConnection.id == connection_id)
        conn = (await self.db.execute(stmt)).scalar_one_or_none()
        if conn:
            summary = dict(conn.sync_summary or {})
            summary["products"] = summary.get("products", 0) + products_delta
            summary["customers"] = summary.get("customers", 0) + customers_delta
            summary["orders"] = summary.get("orders", 0) + orders_delta
            conn.sync_summary = summary
            conn.last_sync_at = datetime.now(timezone.utc)
            conn.sync_status = "completed"

    async def _mark_merchant_onboarding(self, merchant_id: uuid.UUID, store_mode: str):
        stmt = select(Merchant).where(Merchant.id == merchant_id)
        m = (await self.db.execute(stmt)).scalar_one_or_none()
        if m:
            settings_dict = dict(m.settings or {})
            onboarding = settings_dict.get("onboarding", {})
            onboarding["completed"] = True
            onboarding["step"] = "payment_setup"
            onboarding["store_mode"] = store_mode
            onboarding["store_connected"] = True
            settings_dict["onboarding"] = onboarding
            m.settings = settings_dict
