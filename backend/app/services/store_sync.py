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

import base64
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
from app.schemas.product import ShopifySyncResult
from app.services.audit_service import AuditService
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


def verify_shopify_webhook_signature(raw_body: bytes, hmac_header: str, secret: str) -> bool:
    """
    Verify Shopify webhook HMAC-SHA256 signature against raw request body bytes.
    Shopify computes HMAC-SHA256 using the client secret and base64-encodes the digest.
    """
    if not hmac_header or not secret:
        return False
    digest = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).digest()
    computed_hmac = base64.b64encode(digest).decode("utf-8")
    return hmac.compare_digest(computed_hmac, hmac_header.strip())



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

        scopes = "read_products,write_products,read_orders,read_inventory,write_inventory,read_customers"
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
        scopes = token_data.get("scope", "read_products,write_products,read_orders,read_inventory,write_inventory,read_customers")

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
        image_url: str | None = None,
    ) -> Product:
        clean_external_id = str(external_id).strip()
        if "gid://shopify/Product/" in clean_external_id:
            clean_external_id = clean_external_id.split("/")[-1]

        # 1. Check existing external entity mapping
        stmt = select(StoreEntityMapping).where(
            StoreEntityMapping.merchant_id == merchant_id,
            StoreEntityMapping.connection_id == connection_id,
            StoreEntityMapping.entity_type == "product",
            StoreEntityMapping.external_id == clean_external_id,
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
                if currency:
                    product.currency = currency
                if image_url:
                    product.image_url = image_url

                # If SKU is provided and changed, ensure no collision before updating
                if sku and sku != product.sku:
                    sku_check = await self.db.execute(
                        select(Product.id).where(
                            Product.merchant_id == merchant_id,
                            Product.sku == sku,
                            Product.id != product.id,
                        )
                    )
                    if not sku_check.scalar_one_or_none():
                        product.sku = sku

                product.updated_at = datetime.now(timezone.utc)

                # Update or create inventory
                inv_stmt = select(Inventory).where(Inventory.product_id == product.id)
                inv = (await self.db.execute(inv_stmt)).scalar_one_or_none()
                if inv:
                    inv.quantity = max(0, quantity)
                else:
                    self.db.add(
                        Inventory(
                            product_id=product.id,
                            merchant_id=merchant_id,
                            quantity=max(0, quantity),
                            reserved=0,
                        )
                    )
                return product

        # 2. Check if a product with the same SKU already exists for this merchant
        # Links existing unmapped products without creating duplicates
        if sku:
            existing_sku_stmt = select(Product).where(
                Product.merchant_id == merchant_id,
                Product.sku == sku,
            )
            existing_product = (await self.db.execute(existing_sku_stmt)).scalar_one_or_none()
            if existing_product:
                existing_product.name = name
                existing_product.price = price
                existing_product.compare_at_price = compare_at_price
                existing_product.description = description
                existing_product.status = status if status in ("active", "draft", "archived") else "active"
                if currency:
                    existing_product.currency = currency
                if image_url:
                    existing_product.image_url = image_url
                existing_product.updated_at = datetime.now(timezone.utc)

                inv_stmt = select(Inventory).where(Inventory.product_id == existing_product.id)
                inv = (await self.db.execute(inv_stmt)).scalar_one_or_none()
                if inv:
                    inv.quantity = max(0, quantity)
                else:
                    self.db.add(
                        Inventory(
                            product_id=existing_product.id,
                            merchant_id=merchant_id,
                            quantity=max(0, quantity),
                            reserved=0,
                        )
                    )

                # Save mapping so future updates match immediately
                new_mapping = StoreEntityMapping(
                    merchant_id=merchant_id,
                    connection_id=connection_id,
                    entity_type="product",
                    external_id=clean_external_id,
                    internal_id=existing_product.id,
                )
                self.db.add(new_mapping)
                return existing_product

        # 3. Resolve category if provided
        category_id = None
        if category_name:
            c_stmt = select(Category).where(
                Category.merchant_id == merchant_id, Category.name == category_name
            )
            cat = (await self.db.execute(c_stmt)).scalar_one_or_none()
            if cat:
                category_id = cat.id

        # 4. Generate unique SKU if conflicted
        base_sku = sku or f"EXT-{clean_external_id[:8]}"
        sku_check = await self.db.execute(
            select(Product.id).where(Product.merchant_id == merchant_id, Product.sku == base_sku)
        )
        if sku_check.scalar_one_or_none():
            base_sku = f"{base_sku}-{uuid.uuid4().hex[:4]}"

        # 5. Generate unique slug
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
            image_url=image_url,
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
            external_id=clean_external_id,
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

    async def sync_shopify_store(
        self, connection: StoreConnection, delta_only: bool = False
    ) -> StoreSyncStatusResponse:
        """Fetch real data from Shopify Admin API and idempotently map into Flowmint."""
        creds = decrypt_credentials(connection.encrypted_credentials)
        access_token = creds.get("access_token")
        shop = creds.get("shop")

        connection.sync_status = "running"
        job = StoreSyncJob(
            merchant_id=connection.merchant_id,
            connection_id=connection.id,
            status="running",
            entity_type="delta" if delta_only else "all",
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
                # Register webhooks automatically with Shopify if possible
                await self.register_shopify_webhooks(connection)

                # 1. Sync Products (supports delta sync via updated_at_min)
                if delta_only and connection.last_sync_at:
                    p_url = f"{base_url}/products.json?limit=50&updated_at_min={connection.last_sync_at.isoformat()}"
                else:
                    p_url = f"{base_url}/products.json?limit=50"

                p_res = await client.get(p_url, headers=headers)
                if p_res.status_code == 200:
                    for p in p_res.json().get("products", []):
                        variants = p.get("variants", [])
                        first_var = variants[0] if variants else {}
                        stock = sum(v.get("inventory_quantity", 0) for v in variants)
                        price = Decimal(str(first_var.get("price", "0.00")))
                        compare_at = Decimal(str(first_var.get("compare_at_price"))) if first_var.get("compare_at_price") else None
                        img = p.get("image", {}).get("src") if isinstance(p.get("image"), dict) else None

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
                            image_url=img,
                        )
                        products_count += 1

                # 2. Sync Customers (skip on delta_only)
                if not delta_only:
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

                connection.sync_status = "synced"
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

    async def register_shopify_webhooks(self, connection: StoreConnection):
        """Register product and app lifecycle webhooks with Shopify Admin API."""
        try:
            creds = decrypt_credentials(connection.encrypted_credentials)
            access_token = creds.get("access_token")
            shop = creds.get("shop")
            if not access_token or not shop:
                return

            webhook_base = settings.backend_public_url.rstrip("/")
            webhook_url = f"{webhook_base}/api/v1/stores/shopify/webhook"

            topics = ["products/update", "products/create", "products/delete", "app/uninstalled"]
            api_version = settings.shopify_api_version or "2024-01"
            endpoint = f"https://{shop}/admin/api/{api_version}/webhooks.json"
            headers = {
                "X-Shopify-Access-Token": access_token,
                "Content-Type": "application/json",
            }

            async with httpx.AsyncClient(timeout=10.0) as client:
                for topic in topics:
                    try:
                        resp = await client.post(
                            endpoint,
                            headers=headers,
                            json={
                                "webhook": {
                                    "topic": topic,
                                    "address": webhook_url,
                                    "format": "json",
                                }
                            },
                        )
                        if resp.status_code in (201, 200):
                            logger.info("Registered Shopify webhook %s for %s", topic, shop)
                        elif resp.status_code == 422:
                            logger.debug("Shopify webhook %s already registered for %s", topic, shop)
                        else:
                            logger.warning(
                                "Shopify webhook registration for %s returned %s: %s",
                                topic,
                                resp.status_code,
                                resp.text,
                            )
                    except Exception as err:
                        logger.warning("Failed to register webhook %s: %s", topic, str(err))
        except Exception as e:
            logger.warning("Error during register_shopify_webhooks: %s", str(e))

    async def process_shopify_webhook(
        self,
        shop_domain: str,
        topic: str,
        webhook_id: str | None,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Process verified Shopify webhook event idempotently.
        Supports:
        - products/update, products/create
        - products/delete
        - app/uninstalled
        """
        raw_shop = shop_domain.strip().lower()
        if not raw_shop.endswith(".myshopify.com") and "." not in raw_shop:
            raw_shop_candidate = f"{raw_shop}.myshopify.com"
        else:
            raw_shop_candidate = raw_shop

        # Query active connection for shop_domain
        stmt = select(StoreConnection).where(
            StoreConnection.provider == "shopify",
            (StoreConnection.external_store_id == raw_shop)
            | (StoreConnection.external_store_id == raw_shop_candidate)
            | (StoreConnection.store_url.ilike(f"%{raw_shop}%")),
            StoreConnection.status.in_(["connected", "synced", "syncing"]),
        )
        conn = (await self.db.execute(stmt)).scalar_one_or_none()
        if not conn:
            logger.warning("No active Shopify connection found for domain: %s", raw_shop)
            raise NotFoundError("StoreConnection for Shopify domain", raw_shop)

        # Deduplicate using webhook_id
        if webhook_id:
            dup_stmt = select(StoreSyncJob.id).where(
                StoreSyncJob.connection_id == conn.id,
                StoreSyncJob.entity_type == f"webhook:{webhook_id}",
            )
            if (await self.db.execute(dup_stmt)).scalar_one_or_none():
                logger.info("Shopify webhook %s already processed; skipping duplicate.", webhook_id)
                return {"status": "duplicate_ignored", "webhook_id": webhook_id, "topic": topic}

        # Create record of sync job for audit and deduplication
        job = StoreSyncJob(
            merchant_id=conn.merchant_id,
            connection_id=conn.id,
            status="completed",
            entity_type=f"webhook:{webhook_id}" if webhook_id else "webhook:event",
            records_processed=1,
            records_failed=0,
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            summary_json={"topic": topic, "webhook_id": webhook_id},
        )
        self.db.add(job)

        if topic in ("products/update", "products/create"):
            p_id = str(payload.get("id"))
            variants = payload.get("variants", [])
            first_var = variants[0] if variants else {}
            stock = sum(v.get("inventory_quantity", 0) for v in variants)
            price = Decimal(str(first_var.get("price", "0.00")))
            compare_at = Decimal(str(first_var.get("compare_at_price"))) if first_var.get("compare_at_price") else None
            sku = first_var.get("sku") or f"SHPFY-{p_id}"
            img = payload.get("image", {}).get("src") if isinstance(payload.get("image"), dict) else None

            product = await self._upsert_product(
                merchant_id=conn.merchant_id,
                connection_id=conn.id,
                external_id=p_id,
                name=payload.get("title", "Shopify Product"),
                sku=sku,
                price=price,
                compare_at_price=compare_at,
                description=payload.get("body_html"),
                quantity=stock,
                status="active" if payload.get("status") == "active" else "draft",
                image_url=img,
            )

            conn.last_sync_at = datetime.now(timezone.utc)
            conn.sync_status = "synced"
            conn.last_error = None
            if conn.sync_summary is None:
                conn.sync_summary = {}
            conn.sync_summary["last_event"] = f"{topic}:{p_id}"

            await self.db.commit()
            logger.info("Successfully processed Shopify %s for product %s (%s)", topic, p_id, product.name)
            return {
                "status": "processed",
                "topic": topic,
                "product_id": str(product.id),
                "external_id": p_id,
                "name": product.name,
                "sku": product.sku,
            }

        elif topic == "products/delete":
            p_id = str(payload.get("id"))
            # Soft-archive product
            m_stmt = select(StoreEntityMapping).where(
                StoreEntityMapping.merchant_id == conn.merchant_id,
                StoreEntityMapping.connection_id == conn.id,
                StoreEntityMapping.entity_type == "product",
                StoreEntityMapping.external_id == p_id,
            )
            mapping = (await self.db.execute(m_stmt)).scalar_one_or_none()
            if mapping:
                p_stmt = select(Product).where(Product.id == mapping.internal_id)
                product = (await self.db.execute(p_stmt)).scalar_one_or_none()
                if product:
                    product.status = "archived"
                    product.updated_at = datetime.now(timezone.utc)

            conn.last_sync_at = datetime.now(timezone.utc)
            conn.sync_status = "synced"
            await self.db.commit()
            return {"status": "archived", "topic": topic, "external_id": p_id}

        elif topic == "app/uninstalled":
            conn.status = "disconnected"
            conn.disconnected_at = datetime.now(timezone.utc)
            await self.db.commit()
            return {"status": "disconnected", "topic": topic}

        else:
            conn.last_sync_at = datetime.now(timezone.utc)
            await self.db.commit()
            return {"status": "ignored", "topic": topic}

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

    async def trigger_sync(
        self, merchant_id: uuid.UUID, connection_id: uuid.UUID, delta_only: bool = False
    ) -> StoreSyncStatusResponse:
        conn = await self.get_connection(merchant_id, connection_id)
        if conn.status == "disconnected":
            raise ValidationError("Cannot synchronize a disconnected store.")

        if conn.sync_status == "running":
            raise ConflictError("A synchronization job is already running for this store.")

        if conn.provider == "shopify":
            return await self.sync_shopify_store(conn, delta_only=delta_only)
        elif conn.provider == "woocommerce":
            return await self.sync_woocommerce_store(conn)
        else:
            # Custom store
            conn.last_sync_at = datetime.now(timezone.utc)
            conn.sync_status = "synced"
            await self.db.commit()
            return StoreSyncStatusResponse(
                connection_id=conn.id,
                sync_status="synced",
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

    async def push_product_to_shopify(
        self,
        merchant_id: uuid.UUID,
        product: Product,
        changed_fields: dict[str, Any],
        user_id: uuid.UUID | None = None,
    ) -> ShopifySyncResult:
        """
        Push approved product modifications back to Shopify using the Shopify GraphQL Admin API.
        Enforces tenant isolation, verified entity mappings, scope permissions, and records audit logs.
        """
        # 1. Check if product is mapped to a connected Shopify store
        stmt = (
            select(StoreEntityMapping, StoreConnection)
            .join(StoreConnection, StoreEntityMapping.connection_id == StoreConnection.id)
            .where(
                StoreEntityMapping.merchant_id == merchant_id,
                StoreEntityMapping.entity_type == "product",
                StoreEntityMapping.internal_id == product.id,
            )
        )
        row = (await self.db.execute(stmt)).first()
        if not row:
            # Unmapped product — do not send edits for manually created products
            return ShopifySyncResult(
                success=True,
                status="skipped_local_product",
                message="Product is managed locally in Flowmint and is not linked to an external Shopify store.",
            )

        mapping, conn = row

        if conn.provider != "shopify" or conn.status != "connected":
            return ShopifySyncResult(
                success=False,
                status="failed",
                message=f"Store connection '{conn.store_name}' is not an active connected Shopify store (status: {conn.status}).",
                external_product_id=mapping.external_id,
                errors=["Shopify connection inactive"],
            )

        # 2. Permissions / Scopes verification
        granted_scopes = [s.strip() for s in (conn.scopes or "").split(",") if s.strip()]
        has_write_products = "write_products" in granted_scopes
        has_write_inventory = "write_inventory" in granted_scopes

        if not has_write_products:
            error_msg = (
                "Insufficient Shopify permissions: 'write_products' scope is required to push product updates to Shopify. "
                "Please re-authorize your Shopify store in Flowmint Integrations to grant write permissions."
            )
            await AuditService.log_event(
                db=self.db,
                merchant_id=merchant_id,
                actor_type="user",
                actor_id=str(user_id or merchant_id),
                event_type="product.shopify_sync_failed",
                reason=f"Failed to push product '{product.name}' to Shopify: missing write_products scope",
                execution_result={"errors": [error_msg], "product_id": str(product.id), "sku": product.sku},
            )
            await self.db.commit()
            return ShopifySyncResult(
                success=False,
                status="permission_denied",
                message=error_msg,
                external_product_id=mapping.external_id,
                errors=["Missing scope: write_products"],
            )

        if "inventory_quantity" in changed_fields and not has_write_inventory:
            error_msg = (
                "Insufficient Shopify permissions: 'write_inventory' scope is required to update inventory in Shopify. "
                "Please re-authorize your Shopify store in Flowmint Integrations to grant inventory write permissions."
            )
            await AuditService.log_event(
                db=self.db,
                merchant_id=merchant_id,
                actor_type="user",
                actor_id=str(user_id or merchant_id),
                event_type="product.shopify_sync_failed",
                reason=f"Failed to push inventory for product '{product.name}' to Shopify: missing write_inventory scope",
                execution_result={"errors": [error_msg], "product_id": str(product.id), "sku": product.sku},
            )
            await self.db.commit()
            return ShopifySyncResult(
                success=False,
                status="permission_denied",
                message=error_msg,
                external_product_id=mapping.external_id,
                errors=["Missing scope: write_inventory"],
            )

        # 3. Decrypt credentials
        creds = decrypt_credentials(conn.encrypted_credentials)
        access_token = creds.get("access_token")
        shop = creds.get("shop")
        if not access_token or not shop:
            return ShopifySyncResult(
                success=False,
                status="failed",
                message="Shopify credentials missing or corrupted. Please reconnect the store.",
                external_product_id=mapping.external_id,
                errors=["Invalid credentials"],
            )

        api_version = settings.shopify_api_version or "2024-01"
        graphql_endpoint = f"https://{shop}/admin/api/{api_version}/graphql.json"
        headers = {
            "X-Shopify-Access-Token": access_token,
            "Content-Type": "application/json",
        }

        # Format Global ID
        raw_ext_id = mapping.external_id
        product_gid = raw_ext_id if raw_ext_id.startswith("gid://") else f"gid://shopify/Product/{raw_ext_id}"

        async with httpx.AsyncClient(timeout=20.0) as client:
            try:
                # 4. Fetch existing product variants & locations from Shopify to resolve variant GID and inventory item GID
                query = """
                query getProductAndLocations($id: ID!) {
                  product(id: $id) {
                    id
                    title
                    descriptionHtml
                    status
                    variants(first: 10) {
                      nodes {
                        id
                        sku
                        price
                        compareAtPrice
                        inventoryItem {
                          id
                        }
                      }
                    }
                  }
                  locations(first: 5) {
                    nodes {
                      id
                      name
                      isActive
                    }
                  }
                }
                """
                resp = await client.post(
                    graphql_endpoint,
                    json={"query": query, "variables": {"id": product_gid}},
                    headers=headers,
                )
                if resp.status_code in (401, 403):
                    return ShopifySyncResult(
                        success=False,
                        status="permission_denied",
                        message=f"Shopify Admin API authorization error ({resp.status_code}): {resp.text}",
                        external_product_id=mapping.external_id,
                        errors=[f"HTTP {resp.status_code}: {resp.text}"],
                    )

                if resp.status_code != 200:
                    return ShopifySyncResult(
                        success=False,
                        status="failed",
                        message=f"Shopify Admin API error ({resp.status_code}): {resp.text}",
                        external_product_id=mapping.external_id,
                        errors=[f"HTTP {resp.status_code}: {resp.text}"],
                    )

                gql_data = resp.json()
                if "errors" in gql_data and gql_data["errors"]:
                    err_msgs = [e.get("message", "Shopify error") for e in gql_data["errors"]]
                    is_perm = any("access" in m.lower() or "permission" in m.lower() or "scope" in m.lower() for m in err_msgs)
                    return ShopifySyncResult(
                        success=False,
                        status="permission_denied" if is_perm else "failed",
                        message="; ".join(err_msgs),
                        external_product_id=mapping.external_id,
                        errors=err_msgs,
                    )

                remote_product = gql_data.get("data", {}).get("product")
                if not remote_product:
                    return ShopifySyncResult(
                        success=False,
                        status="failed",
                        message=f"Product with ID {product_gid} was not found on Shopify store.",
                        external_product_id=mapping.external_id,
                        errors=["Product not found on Shopify"],
                    )

                variants = remote_product.get("variants", {}).get("nodes", [])
                primary_variant = variants[0] if variants else None
                locations = [loc for loc in gql_data.get("data", {}).get("locations", {}).get("nodes", []) if loc.get("isActive")]
                primary_location = locations[0] if locations else None

                all_errors = []

                # 5. Update top-level Product fields (title, descriptionHtml, status)
                need_product_update = any(k in changed_fields for k in ("name", "description", "status"))
                if need_product_update:
                    product_input: dict[str, Any] = {"id": product_gid}
                    if "name" in changed_fields:
                        product_input["title"] = changed_fields["name"]
                    if "description" in changed_fields:
                        product_input["descriptionHtml"] = changed_fields["description"] or ""
                    if "status" in changed_fields:
                        st = str(changed_fields["status"]).lower()
                        product_input["status"] = "ACTIVE" if st == "active" else ("ARCHIVED" if st == "archived" else "DRAFT")

                    prod_mutation = """
                    mutation productUpdate($input: ProductInput!) {
                      productUpdate(input: $input) {
                        product {
                          id
                          title
                          status
                        }
                        userErrors {
                          field
                          message
                        }
                      }
                    }
                    """
                    p_upd_resp = await client.post(
                        graphql_endpoint,
                        json={"query": prod_mutation, "variables": {"input": product_input}},
                        headers=headers,
                    )
                    p_upd_json = p_upd_resp.json()
                    user_errors = p_upd_json.get("data", {}).get("productUpdate", {}).get("userErrors", [])
                    if user_errors:
                        all_errors.extend([f"Product: {e.get('message')}" for e in user_errors])

                # 6. Update Variant fields (price, compareAtPrice, sku)
                need_variant_update = any(k in changed_fields for k in ("price", "compare_at_price", "sku"))
                if need_variant_update and primary_variant:
                    var_gid = primary_variant.get("id")
                    var_input: dict[str, Any] = {"id": var_gid}
                    if "price" in changed_fields:
                        var_input["price"] = str(changed_fields["price"])
                    if "compare_at_price" in changed_fields:
                        var_input["compareAtPrice"] = str(changed_fields["compare_at_price"]) if changed_fields["compare_at_price"] is not None else None
                    if "sku" in changed_fields:
                        var_input["sku"] = changed_fields["sku"]

                    var_mutation = """
                    mutation productVariantsBulkUpdate($productId: ID!, $variants: [ProductVariantsBulkInput!]!) {
                      productVariantsBulkUpdate(productId: $productId, variants: $variants) {
                        productVariants {
                          id
                          sku
                          price
                          compareAtPrice
                        }
                        userErrors {
                          field
                          message
                        }
                      }
                    }
                    """
                    v_upd_resp = await client.post(
                        graphql_endpoint,
                        json={"query": var_mutation, "variables": {"productId": product_gid, "variants": [var_input]}},
                        headers=headers,
                    )
                    v_upd_json = v_upd_resp.json()
                    v_user_errors = v_upd_json.get("data", {}).get("productVariantsBulkUpdate", {}).get("userErrors", [])
                    if v_user_errors:
                        all_errors.extend([f"Variant: {e.get('message')}" for e in v_user_errors])

                # 7. Update Inventory quantity
                if "inventory_quantity" in changed_fields and primary_variant and primary_location:
                    inv_item = primary_variant.get("inventoryItem")
                    if inv_item:
                        inv_mutation = """
                        mutation inventorySetQuantities($input: InventorySetQuantitiesInput!) {
                          inventorySetQuantities(input: $input) {
                            inventoryAdjustmentGroup {
                              reason
                              changes {
                                name
                                delta
                                quantityAfterChange
                              }
                            }
                            userErrors {
                              field
                              message
                            }
                          }
                        }
                        """
                        inv_input = {
                            "reason": "correction",
                            "name": "available",
                            "ignoreCompareQuantity": True,
                            "quantities": [
                                {
                                    "inventoryItemId": inv_item["id"],
                                    "locationId": primary_location["id"],
                                    "quantity": int(changed_fields["inventory_quantity"]),
                                }
                            ],
                        }
                        inv_resp = await client.post(
                            graphql_endpoint,
                            json={"query": inv_mutation, "variables": {"input": inv_input}},
                            headers=headers,
                        )
                        inv_json = inv_resp.json()
                        inv_user_errors = inv_json.get("data", {}).get("inventorySetQuantities", {}).get("userErrors", [])
                        if inv_user_errors:
                            all_errors.extend([f"Inventory: {e.get('message')}" for e in inv_user_errors])

                if all_errors:
                    await AuditService.log_event(
                        db=self.db,
                        merchant_id=merchant_id,
                        actor_type="user",
                        actor_id=str(user_id or merchant_id),
                        event_type="product.shopify_sync_failed",
                        reason=f"Shopify rejected updates for '{product.name}': {', '.join(all_errors)}",
                        execution_result={"errors": all_errors, "product_id": str(product.id)},
                    )
                    await self.db.commit()
                    return ShopifySyncResult(
                        success=False,
                        status="failed",
                        message=f"Shopify rejected product update: {'; '.join(all_errors)}",
                        external_product_id=mapping.external_id,
                        errors=all_errors,
                    )

                # 8. Success: Update connection last sync timestamp & write audit log
                conn.last_sync_at = datetime.now(timezone.utc)
                await AuditService.log_event(
                    db=self.db,
                    merchant_id=merchant_id,
                    actor_type="user",
                    actor_id=str(user_id or merchant_id),
                    event_type="product.shopify_synced",
                    reason=f"Successfully pushed product '{product.name}' (SKU: {product.sku}) updates to Shopify store",
                    new_status=product.status,
                    execution_result={
                        "product_id": str(product.id),
                        "external_id": mapping.external_id,
                        "fields_updated": list(changed_fields.keys()),
                    },
                )
                await self.db.commit()

                return ShopifySyncResult(
                    success=True,
                    status="pushed",
                    message=f"Successfully synchronized product '{product.name}' to Shopify store '{conn.store_name}'.",
                    external_product_id=mapping.external_id,
                    reconciled=True,
                )

            except Exception as e:
                logger.exception("Error pushing product to Shopify: %s", e)
                return ShopifySyncResult(
                    success=False,
                    status="failed",
                    message=f"Network or API failure pushing to Shopify: {str(e)}",
                    external_product_id=mapping.external_id,
                    errors=[str(e)],
                )
