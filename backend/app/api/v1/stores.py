"""
Store integration endpoints — Shopify, WooCommerce, Custom Store, and Onboarding.

Multi-tenant: every operation enforces user.merchant_id isolation.
Public callback/ingest endpoints validate OAuth HMAC or store API keys.
"""

import uuid
from datetime import datetime, timezone
from typing import Any
from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user
from app.config import get_settings
from app.core.exceptions import AuthenticationError, NotFoundError, ValidationError
from app.database import get_db
from app.models.merchant import Merchant
from app.models.store_connection import StoreConnection
from app.schemas.common import ApiResponse
from app.schemas.store import (
    CustomIngestCustomersRequest,
    CustomIngestOrdersRequest,
    CustomIngestProductsRequest,
    CustomIngestResult,
    CustomStoreConnectRequest,
    CustomStoreConnectResponse,
    OnboardingStatusResponse,
    OnboardingStepUpdateRequest,
    ShopifyAuthInitRequest,
    ShopifyAuthInitResponse,
    StoreConnectionResponse,
    StoreSyncStatusResponse,
    WooCommerceConnectRequest,
)
from app.services.store_sync import StoreSyncService

router = APIRouter(prefix="/stores", tags=["Stores & Onboarding"])
settings = get_settings()


# ==========================================
# STORE CONNECTION MANAGEMENT
# ==========================================

@router.get("", response_model=ApiResponse[list[StoreConnectionResponse]])
async def list_connections(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List connected stores for the authenticated merchant."""
    service = StoreSyncService(db)
    connections = await service.get_connections(user.merchant_id)
    return ApiResponse.ok(connections)


@router.get("/{connection_id}", response_model=ApiResponse[StoreConnectionResponse])
async def get_connection(
    connection_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = StoreSyncService(db)
    conn = await service.get_connection(user.merchant_id, connection_id)
    return ApiResponse.ok(StoreConnectionResponse.model_validate(conn))


@router.post("/{connection_id}/sync", response_model=ApiResponse[StoreSyncStatusResponse])
async def sync_store(
    connection_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Trigger real-time synchronization for a connected store."""
    service = StoreSyncService(db)
    result = await service.trigger_sync(user.merchant_id, connection_id)
    return ApiResponse.ok(result)


@router.post("/{connection_id}/disconnect", response_model=ApiResponse[StoreConnectionResponse])
async def disconnect_store(
    connection_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Disconnect a store integration without deleting historical records."""
    service = StoreSyncService(db)
    result = await service.disconnect(user.merchant_id, connection_id)
    return ApiResponse.ok(result)


# ==========================================
# SHOPIFY OAUTH
# ==========================================

@router.post("/shopify/authorize", response_model=ApiResponse[ShopifyAuthInitResponse])
async def initiate_shopify_oauth(
    data: ShopifyAuthInitRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate Shopify OAuth URL or explain configuration if credentials are not set."""
    service = StoreSyncService(db)
    res = await service.initiate_shopify_oauth(user.merchant_id, data)
    return ApiResponse.ok(res)


@router.get("/shopify/callback")
async def shopify_callback(
    request: Request,
    code: str = Query(...),
    shop: str = Query(...),
    state: str = Query(...),
    hmac: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Public Shopify OAuth callback receiver.
    Validates HMAC signature and state token, exchanges code for token, and redirects frontend.
    """
    query_params = dict(request.query_params)
    service = StoreSyncService(db)
    try:
        await service.handle_shopify_callback(
            code=code,
            shop=shop,
            state=state,
            hmac_str=hmac,
            query_params=query_params,
        )
        return RedirectResponse(
            url=f"{settings.frontend_url}/onboarding/connect-store?status=connected&provider=shopify",
            status_code=302,
        )
    except Exception as e:
        logger_error = str(e)
        return RedirectResponse(
            url=f"{settings.frontend_url}/onboarding/connect-store?status=error&message={logger_error}",
            status_code=302,
        )


# ==========================================
# WOOCOMMERCE
# ==========================================

@router.post("/woocommerce/connect", response_model=ApiResponse[StoreConnectionResponse])
async def connect_woocommerce(
    data: WooCommerceConnectRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Connect WooCommerce REST API with SSRF verification."""
    service = StoreSyncService(db)
    conn = await service.connect_woocommerce(user.merchant_id, data)
    return ApiResponse.ok(StoreConnectionResponse.model_validate(conn))


# ==========================================
# CUSTOM STORE
# ==========================================

@router.post("/custom/connect", response_model=ApiResponse[CustomStoreConnectResponse])
async def connect_custom_store(
    data: CustomStoreConnectRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Connect a custom storefront and generate ingestion API keys."""
    service = StoreSyncService(db)
    res = await service.connect_custom_store(user.merchant_id, data)
    return ApiResponse.ok(res)


@router.post("/custom/{connection_id}/ingest/products", response_model=ApiResponse[CustomIngestResult])
async def ingest_products(
    connection_id: uuid.UUID,
    data: CustomIngestProductsRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Ingest catalog products from a custom store."""
    service = StoreSyncService(db)
    # Validate connection ownership
    await service.get_connection(user.merchant_id, connection_id)
    result = await service.ingest_products(user.merchant_id, connection_id, data.products)
    return ApiResponse.ok(result)


@router.post("/custom/{connection_id}/ingest/customers", response_model=ApiResponse[CustomIngestResult])
async def ingest_customers(
    connection_id: uuid.UUID,
    data: CustomIngestCustomersRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Ingest customer profiles from a custom store."""
    service = StoreSyncService(db)
    await service.get_connection(user.merchant_id, connection_id)
    result = await service.ingest_customers(user.merchant_id, connection_id, data.customers)
    return ApiResponse.ok(result)


@router.post("/custom/{connection_id}/ingest/orders", response_model=ApiResponse[CustomIngestResult])
async def ingest_orders(
    connection_id: uuid.UUID,
    data: CustomIngestOrdersRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Ingest order records from a custom store."""
    service = StoreSyncService(db)
    await service.get_connection(user.merchant_id, connection_id)
    result = await service.ingest_orders(user.merchant_id, connection_id, data.orders)
    return ApiResponse.ok(result)


# ==========================================
# ONBOARDING ENDPOINTS
# ==========================================

onboarding_router = APIRouter(prefix="/onboarding", tags=["Onboarding"])


@onboarding_router.get("/status", response_model=ApiResponse[OnboardingStatusResponse])
async def get_onboarding_status(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get persistent onboarding status for the current merchant.
    Determines whether Connect Store must be shown.
    """
    m_stmt = select(Merchant).where(Merchant.id == user.merchant_id)
    merchant = (await db.execute(m_stmt)).scalar_one_or_none()
    if not merchant:
        raise NotFoundError("Merchant", str(user.merchant_id))

    m_settings = merchant.settings or {}
    onboarding_data = m_settings.get("onboarding", {})

    # Check store connections
    conn_stmt = (
        select(StoreConnection)
        .where(
            StoreConnection.merchant_id == user.merchant_id,
            StoreConnection.status.in_(["connected", "synced", "syncing"]),
        )
        .order_by(StoreConnection.created_at.desc())
    )
    active_conn = (await db.execute(conn_stmt)).scalars().first()

    has_store = active_conn is not None
    is_completed = onboarding_data.get("completed", False) or has_store

    active_resp = StoreConnectionResponse.model_validate(active_conn) if active_conn else None
    step = onboarding_data.get("step", "connect_store" if not is_completed else "completed")

    return ApiResponse.ok(
        OnboardingStatusResponse(
            onboarding_completed=is_completed,
            onboarding_step=step,
            store_connected=has_store,
            store_mode=onboarding_data.get("store_mode", active_conn.provider if active_conn else None),
            active_store=active_resp,
            payment_mode=m_settings.get("payment_config", {}).get("mode"),
            razorpay_mode=settings.razorpay_mode,
            razorpay_configured=bool(settings.razorpay_key_id and settings.razorpay_key_secret),
        )
    )


@onboarding_router.post("/skip", response_model=ApiResponse[OnboardingStatusResponse])
async def skip_onboarding(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Mark onboarding as manually completed / skipped without fabricating a store connection.
    """
    m_stmt = select(Merchant).where(Merchant.id == user.merchant_id)
    merchant = (await db.execute(m_stmt)).scalar_one_or_none()
    if not merchant:
        raise NotFoundError("Merchant", str(user.merchant_id))

    settings_dict = dict(merchant.settings or {})
    settings_dict["onboarding"] = {
        "completed": True,
        "step": "completed",
        "store_mode": "manual",
        "store_connected": False,
        "skipped_at": str(datetime.now(timezone.utc)),
    }
    merchant.settings = settings_dict
    await db.commit()

    return ApiResponse.ok(
        OnboardingStatusResponse(
            onboarding_completed=True,
            onboarding_step="completed",
            store_connected=False,
            store_mode="manual",
            active_store=None,
            razorpay_mode=settings.razorpay_mode,
            razorpay_configured=bool(settings.razorpay_key_id and settings.razorpay_key_secret),
        )
    )


@onboarding_router.post("/step", response_model=ApiResponse[OnboardingStatusResponse])
async def update_onboarding_step(
    data: OnboardingStepUpdateRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update onboarding step (e.g., transition to payment_setup or completed)."""
    m_stmt = select(Merchant).where(Merchant.id == user.merchant_id)
    merchant = (await db.execute(m_stmt)).scalar_one_or_none()
    if not merchant:
        raise NotFoundError("Merchant", str(user.merchant_id))

    settings_dict = dict(merchant.settings or {})
    onboarding = settings_dict.get("onboarding", {})
    onboarding["step"] = data.step
    if data.step == "completed":
        onboarding["completed"] = True
    if data.metadata:
        onboarding.update(data.metadata)
    settings_dict["onboarding"] = onboarding
    merchant.settings = settings_dict
    await db.commit()

    return await get_onboarding_status(user, db)
