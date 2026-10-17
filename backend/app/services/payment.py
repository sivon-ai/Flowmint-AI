"""
Payment service — Razorpay TEST integration with state machine.

Payment lifecycle: pending → authorized → captured (or → failed at any step)
Webhook flow: verify signature → deduplicate → validate transition → update state

CRITICAL: Webhook is the authoritative payment state. Frontend verification is backup only.
"""

import hashlib
import hmac
import logging
import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.exceptions import (
    DuplicateError,
    InvalidStateTransitionError,
    NotFoundError,
    PaymentError,
    ValidationError,
)
from app.events.bus import DomainEvent, event_bus
from app.events.types import EventType
from app.models.order import Order
from app.models.outbox import OutboxEvent
from app.models.payment import PAYMENT_TRANSITIONS, Payment, PaymentEvent
from app.schemas.payment import PaymentResponse, RazorpayOrderResponse

logger = logging.getLogger(__name__)
settings = get_settings()


class PaymentService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def initiate(
        self,
        merchant_id: uuid.UUID,
        order_id: uuid.UUID,
        idempotency_key: str | None = None,
    ) -> RazorpayOrderResponse:
        """
        Create a Razorpay order and a Payment record.
        Ensures idempotency, prevents duplicate pending payments, and never marks order as paid on failure.
        """
        # Get order
        result = await self.db.execute(
            select(Order).where(
                Order.id == order_id, Order.merchant_id == merchant_id
            )
        )
        order = result.scalar_one_or_none()
        if not order:
            raise NotFoundError("Order", str(order_id))
        if order.status != "pending":
            raise ValidationError(f"Order is in '{order.status}' status — cannot initiate payment")

        # Resolve merchant name and custom Razorpay keys if configured
        from app.models.merchant import Merchant
        from app.core.encryption import decrypt_credentials

        m_result = await self.db.execute(
            select(Merchant).where(Merchant.id == merchant_id)
        )
        merchant = m_result.scalar_one_or_none()
        merchant_name = merchant.name if merchant else "Flowmint Store"

        app_settings = get_settings()
        key_id = app_settings.razorpay_key_id
        key_secret = app_settings.razorpay_key_secret
        if merchant and merchant.settings and "payment_config" in merchant.settings:
            p_conf = merchant.settings["payment_config"]
            if p_conf.get("razorpay_key_id"):
                key_id = p_conf["razorpay_key_id"]
            if p_conf.get("razorpay_key_secret"):
                try:
                    dec = decrypt_credentials(p_conf["razorpay_key_secret"])
                    key_secret = dec.get("secret", key_secret)
                except Exception as dec_err:
                    logger.warning("Could not decrypt merchant razorpay_key_secret: %s", dec_err)

        amount_paise = int(order.total * 100)

        # Check for existing pending or authorized payment for this order (prevent duplicate pending payments)
        existing = await self.db.execute(
            select(Payment).where(
                Payment.order_id == order_id,
                Payment.status.in_(["pending", "authorized"]),
            )
        )
        existing_payment = existing.scalar_one_or_none()
        if existing_payment:
            # If an order already has an active provider order id, return existing details idempotently
            if existing_payment.provider_order_id:
                return RazorpayOrderResponse(
                    payment_id=existing_payment.id,
                    razorpay_order_id=existing_payment.provider_order_id,
                    razorpay_key_id=key_id,
                    amount=amount_paise,
                    currency=order.currency,
                    order_number=order.order_number,
                    merchant_name=merchant_name,
                )
            raise PaymentError("A payment is already in progress for this order")

        # Check idempotency key if explicitly supplied
        actual_idempotency_key = idempotency_key or f"pay_{order_id}_{uuid.uuid4().hex[:12]}"
        if idempotency_key:
            existing_by_key = await self.db.execute(
                select(Payment).where(
                    Payment.merchant_id == merchant_id,
                    Payment.idempotency_key == idempotency_key,
                )
            )
            key_payment = existing_by_key.scalar_one_or_none()
            if key_payment:
                if key_payment.provider_order_id:
                    return RazorpayOrderResponse(
                        payment_id=key_payment.id,
                        razorpay_order_id=key_payment.provider_order_id,
                        razorpay_key_id=key_id,
                        amount=amount_paise,
                        currency=order.currency,
                        order_number=order.order_number,
                        merchant_name=merchant_name,
                    )
                raise PaymentError("A payment with this idempotency key is already in progress")

        # Validate gateway credentials exist
        error_ref = f"PAY-ERR-{uuid.uuid4().hex[:8].upper()}"
        if not key_id or not key_secret:
            logger.error(
                "[%s] Missing Razorpay credentials for merchant %s (order %s)",
                error_ref, merchant_id, order_id
            )
            raise PaymentError(
                f"Payment provider configuration is incomplete. Please contact support with reference {error_ref}."
            )

        # Create Razorpay order via SDK
        try:
            import razorpay
            client = razorpay.Client(auth=(key_id, key_secret))
            rz_order = client.order.create({
                "amount": amount_paise,
                "currency": order.currency,
                "receipt": order.order_number,
            })
            provider_order_id = rz_order["id"]
        except Exception as e:
            logger.error(
                "[%s] Razorpay order creation failed for merchant %s, order %s: %s",
                error_ref, merchant_id, order_id, e,
                exc_info=True,
            )
            # Safe customer error without leaking Python module names, tracebacks, or secrets
            raise PaymentError(
                f"Payment provider unavailable. Please try again or quote reference {error_ref} to support."
            )

        # Create payment record
        payment_id = uuid.uuid4()
        payment = Payment(
            id=payment_id,
            order_id=order_id,
            merchant_id=merchant_id,
            amount=order.total,
            currency=order.currency,
            status="pending",
            provider="razorpay",
            provider_order_id=provider_order_id,
            idempotency_key=actual_idempotency_key,
        )
        self.db.add(payment)

        self.db.add(OutboxEvent(
            event_type=EventType.PAYMENT_CREATED,
            aggregate_type="payment",
            aggregate_id=str(payment.id),
            payload={
                "merchant_id": str(merchant_id),
                "order_id": str(order_id),
                "amount": str(order.total),
            },
        ))

        await self.db.commit()
        await self.db.refresh(payment)

        return RazorpayOrderResponse(
            payment_id=payment.id,
            razorpay_order_id=provider_order_id,
            razorpay_key_id=key_id,
            amount=amount_paise,
            currency=order.currency,
            order_number=order.order_number,
            merchant_name=merchant_name,
        )

    async def handle_webhook(self, raw_body: bytes, signature: str) -> dict:
        """
        Process a Razorpay webhook.
        Flow: verify signature → parse → deduplicate → find payment → validate transition → update
        
        This endpoint does NOT require merchant JWT authentication.
        Razorpay signature verification is the authentication mechanism.
        """
        # 1. Verify signature
        if not self._verify_webhook_signature(raw_body, signature):
            raise PaymentError("Invalid webhook signature")

        import json
        try:
            payload = json.loads(raw_body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise ValidationError("Malformed JSON payload")

        if not isinstance(payload, dict):
            raise ValidationError("Invalid webhook payload format")

        event_type = payload.get("event", "")
        event_id = payload.get("event_id") or payload.get("id", "")

        # 2. Extract payment info
        payment_entity = (
            payload.get("payload", {})
            .get("payment", {})
            .get("entity", {})
        )
        if not payment_entity:
            logger.warning(f"Webhook missing payment entity: {event_type}")
            return {"status": "ignored", "reason": "no payment entity"}

        provider_payment_id = payment_entity.get("id", "")
        provider_order_id = payment_entity.get("order_id", "")

        # 3. Deduplicate by provider_event_id
        existing_event = await self.db.execute(
            select(PaymentEvent).where(PaymentEvent.provider_event_id == event_id)
        )
        if existing_event.scalar_one_or_none():
            logger.info(f"Duplicate webhook ignored: {event_id}")
            return {"status": "duplicate", "event_id": event_id}

        # 4. Find internal payment
        result = await self.db.execute(
            select(Payment).where(Payment.provider_order_id == provider_order_id)
        )
        payment = result.scalar_one_or_none()
        if not payment:
            logger.warning(f"Payment not found for provider_order_id: {provider_order_id}")
            return {"status": "not_found", "provider_order_id": provider_order_id}

        # 5. Map Razorpay event to internal status
        new_status = self._map_razorpay_event(event_type)
        if not new_status:
            logger.info(f"Unhandled webhook event type: {event_type}")
            return {"status": "ignored", "event_type": event_type}

        # Check if already processed (repeated event delivery with different event_id)
        if payment.status == new_status:
            logger.info(f"Payment {payment.id} already in status {new_status}")
            return {"status": "already_processed", "payment_status": payment.status}

        # 6. Validate state transition
        if not payment.can_transition_to(new_status):
            logger.warning(
                f"Invalid payment transition: {payment.status} → {new_status} "
                f"for payment {payment.id}"
            )
            # Record the event even if transition is invalid
            self.db.add(PaymentEvent(
                payment_id=payment.id,
                event_type=event_type,
                provider_event_id=event_id,
                raw_payload=payload,
            ))
            await self.db.commit()
            return {"status": "transition_invalid", "from": payment.status, "to": new_status}

        # 7. Update payment
        payment.status = new_status
        payment.provider_payment_id = provider_payment_id
        if new_status == "failed":
            payment.failure_reason = payment_entity.get("error_description", "Payment failed")

        # Record event
        self.db.add(PaymentEvent(
            payment_id=payment.id,
            event_type=event_type,
            provider_event_id=event_id,
            raw_payload=payload,
        ))

        # 8. Update order status if payment captured
        if new_status == "captured":
            order_result = await self.db.execute(
                select(Order).where(Order.id == payment.order_id)
            )
            order = order_result.scalar_one_or_none()
            if order:
                order.status = "confirmed"

                # Confirm inventory sale
                from app.services.inventory import InventoryService
                inv_service = InventoryService(self.db)
                for item in order.items:
                    await inv_service.confirm_sale(
                        order.merchant_id, item.product_id, item.quantity
                    )

        # Outbox event
        event_type_mapped = {
            "captured": EventType.PAYMENT_CAPTURED,
            "failed": EventType.PAYMENT_FAILED,
            "authorized": EventType.PAYMENT_AUTHORIZED,
        }.get(new_status, EventType.PAYMENT_CREATED)

        self.db.add(OutboxEvent(
            event_type=event_type_mapped,
            aggregate_type="payment",
            aggregate_id=str(payment.id),
            payload={
                "merchant_id": str(payment.merchant_id),
                "order_id": str(payment.order_id),
                "status": new_status,
                "amount": str(payment.amount),
            },
        ))

        await self.db.commit()

        # Dispatch event
        await event_bus.publish(DomainEvent(
            event_type=event_type_mapped,
            aggregate_type="payment",
            aggregate_id=str(payment.id),
            payload={
                "order_id": str(payment.order_id),
                "status": new_status,
                "amount": str(payment.amount),
            },
            merchant_id=str(payment.merchant_id),
        ))

        return {"status": "processed", "payment_status": new_status}

    async def get(self, merchant_id: uuid.UUID, payment_id: uuid.UUID) -> PaymentResponse:
        result = await self.db.execute(
            select(Payment).where(
                Payment.id == payment_id, Payment.merchant_id == merchant_id
            )
        )
        payment = result.scalar_one_or_none()
        if not payment:
            raise NotFoundError("Payment", str(payment_id))
        return PaymentResponse.model_validate(payment)

    def _verify_webhook_signature(self, raw_body: bytes, signature: str) -> bool:
        """Verify Razorpay webhook signature using HMAC SHA-256."""
        if not settings.razorpay_webhook_secret:
            logger.error("Razorpay webhook secret not configured")
            return False
        expected = hmac.new(
            settings.razorpay_webhook_secret.encode("utf-8"),
            raw_body,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature)

    @staticmethod
    def _map_razorpay_event(event_type: str) -> str | None:
        """Map Razorpay webhook event type to internal payment status."""
        mapping = {
            "payment.authorized": "authorized",
            "payment.captured": "captured",
            "payment.failed": "failed",
            "order.paid": "captured",
        }
        return mapping.get(event_type)

    async def verify_checkout(
        self,
        merchant_id: uuid.UUID,
        payment_id: uuid.UUID,
        razorpay_order_id: str,
        razorpay_payment_id: str,
        razorpay_signature: str,
    ) -> PaymentResponse:
        """
        Verify the Razorpay checkout signature on backend.
        Binds to merchant, order, amount, and verifies HMAC-SHA256.
        """
        stmt = (
            select(Payment, Order)
            .join(Order, Payment.order_id == Order.id)
            .where(Payment.id == payment_id, Payment.merchant_id == merchant_id)
        )
        row = (await self.db.execute(stmt)).first()
        if not row:
            raise NotFoundError("Payment", str(payment_id))
        payment, order = row

        if payment.provider_order_id != razorpay_order_id:
            logger.warning(
                "Mismatched provider_order_id for payment %s: expected %s, got %s",
                payment.id, payment.provider_order_id, razorpay_order_id
            )
            raise ValidationError("Invalid payment order reference.")

        # Determine secret
        key_secret = get_settings().razorpay_key_secret
        from app.models.merchant import Merchant
        m_stmt = select(Merchant).where(Merchant.id == merchant_id)
        merchant = (await self.db.execute(m_stmt)).scalar_one_or_none()
        if merchant and merchant.settings and "payment_config" in merchant.settings:
            p_conf = merchant.settings["payment_config"]
            if p_conf.get("razorpay_key_secret"):
                from app.core.encryption import decrypt_credentials
                try:
                    dec = decrypt_credentials(p_conf["razorpay_key_secret"])
                    key_secret = dec.get("secret", key_secret)
                except Exception:
                    pass

        # Verify signature: razorpay_order_id + "|" + razorpay_payment_id
        msg = f"{razorpay_order_id}|{razorpay_payment_id}".encode("utf-8")
        expected = hmac.new(key_secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()

        if not hmac.compare_digest(expected, razorpay_signature):
            payment.status = "failed"
            payment.failure_reason = "Signature verification failed"
            await self.db.commit()
            raise PaymentError("Payment signature verification failed. Untrusted checkout.")

        if payment.status != "captured":
            if not payment.can_transition_to("captured"):
                raise InvalidStateTransitionError("Payment", payment.status, "captured")

            payment.status = "captured"
            payment.provider_payment_id = razorpay_payment_id
            order.status = "confirmed"

            # Confirm inventory sale
            from app.services.inventory import InventoryService
            inv_service = InventoryService(self.db)
            for item in order.items:
                await inv_service.confirm_sale(order.merchant_id, item.product_id, item.quantity)

            # Record event
            self.db.add(PaymentEvent(
                payment_id=payment.id,
                event_type="payment.captured",
                provider_event_id=f"checkout_{razorpay_payment_id}",
                raw_payload={"source": "checkout_verification", "razorpay_payment_id": razorpay_payment_id},
            ))

            self.db.add(OutboxEvent(
                event_type=EventType.PAYMENT_CAPTURED,
                aggregate_type="payment",
                aggregate_id=str(payment.id),
                payload={
                    "merchant_id": str(payment.merchant_id),
                    "order_id": str(payment.order_id),
                    "status": "captured",
                    "amount": str(payment.amount),
                },
            ))

            await self.db.commit()

        return PaymentResponse.model_validate(payment)

    async def get_payment_config(self, merchant_id: uuid.UUID) -> dict:
        from app.models.merchant import Merchant
        stmt = select(Merchant).where(Merchant.id == merchant_id)
        merchant = (await self.db.execute(stmt)).scalar_one_or_none()
        m_settings = (merchant.settings or {}) if merchant else {}
        p_conf = m_settings.get("payment_config", {})
        key_id = p_conf.get("razorpay_key_id") or settings.razorpay_key_id
        mode = p_conf.get("razorpay_mode") or settings.razorpay_mode or "test"
        configured = bool(key_id and (p_conf.get("razorpay_key_secret") or settings.razorpay_key_secret))

        masked_key = (key_id[:10] + "...") if key_id and len(key_id) > 10 else key_id
        return {
            "payment_mode": p_conf.get("payment_mode", "store_native"),
            "razorpay_mode": mode,
            "razorpay_key_id": masked_key,
            "razorpay_configured": configured,
            "webhook_url": f"{settings.backend_public_url}/api/v1/payments/webhook",
        }

    async def update_payment_config(self, merchant_id: uuid.UUID, data: dict) -> dict:
        from app.models.merchant import Merchant
        from app.core.encryption import encrypt_credentials
        stmt = select(Merchant).where(Merchant.id == merchant_id)
        merchant = (await self.db.execute(stmt)).scalar_one_or_none()
        if not merchant:
            raise NotFoundError("Merchant", str(merchant_id))

        m_settings = dict(merchant.settings or {})
        p_conf = dict(m_settings.get("payment_config", {}))

        # Update payment mode if provided
        if data.get("payment_mode"):
            p_conf["payment_mode"] = data["payment_mode"]
        elif "payment_mode" not in p_conf:
            p_conf["payment_mode"] = "store_native"

        # Update gateway keys only when non-empty string provided (never overwrite with empty or None)
        if data.get("razorpay_key_id") and str(data["razorpay_key_id"]).strip():
            p_conf["razorpay_key_id"] = str(data["razorpay_key_id"]).strip()

        if data.get("razorpay_key_secret") and str(data["razorpay_key_secret"]).strip():
            p_conf["razorpay_key_secret"] = encrypt_credentials({"secret": str(data["razorpay_key_secret"]).strip()})

        if data.get("razorpay_webhook_secret") and str(data["razorpay_webhook_secret"]).strip():
            p_conf["razorpay_webhook_secret"] = encrypt_credentials({"secret": str(data["razorpay_webhook_secret"]).strip()})

        # Update environment mode if provided (default test; never switch to live automatically)
        if data.get("razorpay_mode"):
            p_conf["razorpay_mode"] = data["razorpay_mode"]
        elif "razorpay_mode" not in p_conf:
            p_conf["razorpay_mode"] = "test"

        m_settings["payment_config"] = p_conf

        # Update onboarding step to completed
        onboarding = dict(m_settings.get("onboarding", {}))
        onboarding["completed"] = True
        onboarding["step"] = "completed"
        onboarding["payment_mode"] = p_conf["payment_mode"]
        m_settings["onboarding"] = onboarding

        merchant.settings = m_settings
        await self.db.commit()

        return await self.get_payment_config(merchant_id)
