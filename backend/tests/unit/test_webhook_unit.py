"""
Unit tests for Razorpay Webhook Processing.

Tests:
- Valid webhook signature calculation & verification
- Invalid signature rejection
- Malformed JSON payload handling
- Unknown payment handling
- Duplicate webhook handling (by provider_event_id)
- Repeated event delivery (same status)
- Invalid payment transition
"""

import hashlib
import hmac
import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config import get_settings
from app.core.exceptions import PaymentError, ValidationError
from app.models.payment import Payment
from app.services.payment import PaymentService


def _sign(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


class TestRazorpayWebhookUnit:
    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        return db

    @pytest.fixture
    def payment_service(self, mock_db):
        return PaymentService(db=mock_db)

    def test_signature_verification_success(self, payment_service):
        secret = get_settings().razorpay_webhook_secret or "test_secret_123"
        with patch.object(get_settings(), "razorpay_webhook_secret", secret):
            body = b'{"event": "payment.captured"}'
            sig = _sign(body, secret)
            assert payment_service._verify_webhook_signature(body, sig) is True

    def test_signature_verification_failure(self, payment_service):
        secret = get_settings().razorpay_webhook_secret or "test_secret_123"
        with patch.object(get_settings(), "razorpay_webhook_secret", secret):
            body = b'{"event": "payment.captured"}'
            assert payment_service._verify_webhook_signature(body, "invalid_sig") is False

    @pytest.mark.asyncio
    async def test_webhook_rejects_invalid_signature(self, payment_service):
        body = b'{"event": "payment.captured"}'
        with patch.object(payment_service, "_verify_webhook_signature", return_value=False):
            with pytest.raises(PaymentError, match="Invalid webhook signature"):
                await payment_service.handle_webhook(body, "bad_signature")

    @pytest.mark.asyncio
    async def test_webhook_rejects_malformed_json(self, payment_service):
        body = b'{"event": broken_json'
        with patch.object(payment_service, "_verify_webhook_signature", return_value=True):
            with pytest.raises(ValidationError, match="Malformed JSON payload"):
                await payment_service.handle_webhook(body, "valid_sig")

    @pytest.mark.asyncio
    async def test_webhook_duplicate_event_id(self, payment_service, mock_db):
        payload = {
            "event": "payment.captured",
            "event_id": "evt_duplicate_001",
            "payload": {
                "payment": {
                    "entity": {"id": "pay_1", "order_id": "order_rzp_1"}
                }
            },
        }
        body = json.dumps(payload).encode()

        # Mock existing event found
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = MagicMock()
        mock_db.execute.return_value = mock_result

        with patch.object(payment_service, "_verify_webhook_signature", return_value=True):
            result = await payment_service.handle_webhook(body, "valid_sig")
            assert result["status"] == "duplicate"
            assert result["event_id"] == "evt_duplicate_001"

    @pytest.mark.asyncio
    async def test_webhook_unknown_payment(self, payment_service, mock_db):
        payload = {
            "event": "payment.captured",
            "event_id": "evt_new_001",
            "payload": {
                "payment": {
                    "entity": {"id": "pay_1", "order_id": "order_unknown_123"}
                }
            },
        }
        body = json.dumps(payload).encode()

        # Mock event not found (execute #1), then payment not found (execute #2)
        mock_evt_result = MagicMock()
        mock_evt_result.scalar_one_or_none.return_value = None
        mock_pay_result = MagicMock()
        mock_pay_result.scalar_one_or_none.return_value = None
        mock_db.execute.side_effect = [mock_evt_result, mock_pay_result]

        with patch.object(payment_service, "_verify_webhook_signature", return_value=True):
            result = await payment_service.handle_webhook(body, "valid_sig")
            assert result["status"] == "not_found"
            assert result["provider_order_id"] == "order_unknown_123"

    @pytest.mark.asyncio
    async def test_webhook_repeated_event_delivery(self, payment_service, mock_db):
        """If payment is already in the requested status, acknowledge idempotently."""
        payload = {
            "event": "payment.captured",
            "event_id": "evt_repeated_002",
            "payload": {
                "payment": {
                    "entity": {"id": "pay_1", "order_id": "order_captured_123"}
                }
            },
        }
        body = json.dumps(payload).encode()

        mock_payment = Payment(
            status="captured",
            provider_order_id="order_captured_123",
            idempotency_key="k1",
        )

        mock_evt_result = MagicMock()
        mock_evt_result.scalar_one_or_none.return_value = None
        mock_pay_result = MagicMock()
        mock_pay_result.scalar_one_or_none.return_value = mock_payment
        mock_db.execute.side_effect = [mock_evt_result, mock_pay_result]

        with patch.object(payment_service, "_verify_webhook_signature", return_value=True):
            result = await payment_service.handle_webhook(body, "valid_sig")
            assert result["status"] == "already_processed"
            assert result["payment_status"] == "captured"

    @pytest.mark.asyncio
    async def test_webhook_invalid_payment_transition(self, payment_service, mock_db):
        """Failed payment cannot transition to captured."""
        payload = {
            "event": "payment.captured",
            "event_id": "evt_invalid_003",
            "payload": {
                "payment": {
                    "entity": {"id": "pay_1", "order_id": "order_failed_123"}
                }
            },
        }
        body = json.dumps(payload).encode()

        mock_payment = Payment(
            status="failed",
            provider_order_id="order_failed_123",
            idempotency_key="k2",
        )

        mock_evt_result = MagicMock()
        mock_evt_result.scalar_one_or_none.return_value = None
        mock_pay_result = MagicMock()
        mock_pay_result.scalar_one_or_none.return_value = mock_payment
        mock_db.execute.side_effect = [mock_evt_result, mock_pay_result]

        with patch.object(payment_service, "_verify_webhook_signature", return_value=True):
            result = await payment_service.handle_webhook(body, "valid_sig")
            assert result["status"] == "transition_invalid"
            assert result["from"] == "failed"
            assert result["to"] == "captured"

    def test_map_razorpay_events(self, payment_service):
        assert payment_service._map_razorpay_event("payment.authorized") == "authorized"
        assert payment_service._map_razorpay_event("payment.captured") == "captured"
        assert payment_service._map_razorpay_event("payment.failed") == "failed"
        assert payment_service._map_razorpay_event("order.paid") == "captured"
        assert payment_service._map_razorpay_event("unknown.event") is None
