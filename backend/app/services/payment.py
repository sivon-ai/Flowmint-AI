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
        self, merchant_id: uuid.UUID, order_id: uuid.UUID
    ) -> RazorpayOrderResponse:
        """
        Create a Razorpay order and a Payment record.
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

        # Check for existing pending payment
        existing = await self.db.execute(
            select(Payment).where(
                Payment.order_id == order_id,
                Payment.status.in_(["pending", "authorized"]),
            )
        )
        if existing.scalar_one_or_none():
            raise PaymentError("A payment is already in progress for this order")

        # Create Razorpay order
        amount_paise = int(order.total * 100)
        idempotency_key = f"pay_{order_id}_{uuid.uuid4().hex[:8]}"

        try:
            import razorpay
            client = razorpay.Client(auth=(settings.razorpay_key_id, settings.razorpay_key_secret))
            rz_order = client.order.create({
                "amount": amount_paise,
                "currency": order.currency,
                "receipt": order.order_number,
            })
            provider_order_id = rz_order["id"]
        except Exception as e:
            logger.error(f"Razorpay order creation failed: {e}")
            raise PaymentError(f"Payment provider error: {str(e)}")

        # Create payment record
        payment = Payment(
            order_id=order_id,
            merchant_id=merchant_id,
            amount=order.total,
            currency=order.currency,
            status="pending",
            provider="razorpay",
            provider_order_id=provider_order_id,
            idempotency_key=idempotency_key,
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

        # Get merchant name
        from app.models.merchant import Merchant
        m_result = await self.db.execute(
            select(Merchant.name).where(Merchant.id == merchant_id)
        )
        merchant_name = m_result.scalar() or "Flowmint Store"

        return RazorpayOrderResponse(
            payment_id=payment.id,
            razorpay_order_id=provider_order_id,
            razorpay_key_id=settings.razorpay_key_id,
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
