"""
Store and Onboarding schemas.

Defines API payloads and safe responses (never exposing credentials/secrets).
"""

import uuid
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field


class StoreConnectionResponse(BaseModel):
    id: uuid.UUID
    merchant_id: uuid.UUID
    provider: str
    store_url: str
    store_name: str | None = None
    external_store_id: str | None = None
    status: str
    scopes: str | None = None
    sync_status: str
    last_sync_at: datetime | None = None
    sync_summary: dict | None = None
    last_error: str | None = None
    disconnected_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ShopifyAuthInitRequest(BaseModel):
    shop_domain: str = Field(..., min_length=3, max_length=255)


class ShopifyAuthInitResponse(BaseModel):
    authorization_url: str | None = None
    state: str | None = None
    configured: bool = True
    message: str | None = None


class WooCommerceConnectRequest(BaseModel):
    store_url: str = Field(..., min_length=8, max_length=500)
    consumer_key: str = Field(..., min_length=10, max_length=255)
    consumer_secret: str = Field(..., min_length=10, max_length=255)
    store_name: str | None = Field(None, max_length=255)


class CustomStoreConnectRequest(BaseModel):
    store_name: str = Field(..., min_length=2, max_length=255)
    store_url: str = Field(..., min_length=4, max_length=500)


class CustomStoreConnectResponse(BaseModel):
    connection: StoreConnectionResponse
    ingestion_api_key: str
    ingestion_endpoint: str
    documentation: dict


class CustomIngestProductItem(BaseModel):
    external_id: str
    name: str
    sku: str
    price: Decimal
    compare_at_price: Decimal | None = None
    currency: str = "INR"
    description: str | None = None
    quantity: int = 0
    status: str = "active"


class CustomIngestCustomerItem(BaseModel):
    external_id: str
    email: str
    name: str
    phone: str | None = None


class CustomIngestOrderItem(BaseModel):
    external_id: str
    order_number: str
    customer_email: str
    customer_name: str
    total: Decimal
    currency: str = "INR"
    status: str = "pending"
    items: list[dict] = Field(default_factory=list)


class CustomIngestProductsRequest(BaseModel):
    products: list[CustomIngestProductItem]


class CustomIngestCustomersRequest(BaseModel):
    customers: list[CustomIngestCustomerItem]


class CustomIngestOrdersRequest(BaseModel):
    orders: list[CustomIngestOrderItem]


class CustomIngestResult(BaseModel):
    entity_type: str
    records_processed: int
    records_failed: int
    errors: list[str] = Field(default_factory=list)


class StoreSyncStatusResponse(BaseModel):
    connection_id: uuid.UUID
    sync_status: str
    last_sync_at: datetime | None = None
    sync_summary: dict = Field(default_factory=dict)
    records_processed: int = 0
    records_failed: int = 0
    last_error: str | None = None


class OnboardingStatusResponse(BaseModel):
    onboarding_completed: bool
    onboarding_step: str  # "connect_store" | "payment_setup" | "completed"
    store_connected: bool
    store_mode: str | None = None  # "shopify" | "woocommerce" | "custom" | "manual"
    active_store: StoreConnectionResponse | None = None
    payment_mode: str | None = None
    razorpay_mode: str = "test"
    razorpay_configured: bool = False


class OnboardingStepUpdateRequest(BaseModel):
    step: str
    metadata: dict | None = None


class PaymentConfigResponse(BaseModel):
    payment_mode: str
    razorpay_mode: str
    razorpay_key_id: str | None = None
    razorpay_configured: bool
    webhook_url: str


class PaymentConfigUpdateRequest(BaseModel):
    payment_mode: str  # "store_native" | "razorpay_reconciliation" | "razorpay_hosted" | "later"
    razorpay_key_id: str | None = None
    razorpay_key_secret: str | None = None
    razorpay_webhook_secret: str | None = None
    razorpay_mode: str = "test"


class PaymentVerifyRequest(BaseModel):
    payment_id: uuid.UUID
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


class PaymentVerifyResponse(BaseModel):
    payment_id: uuid.UUID
    order_id: uuid.UUID
    status: str
    amount: Decimal
    currency: str
