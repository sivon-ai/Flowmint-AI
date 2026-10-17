"""
Unit tests for Razorpay SDK integration, client initialization, error sanitization,
idempotency, and checkout signature verification.

All provider calls are mocked. Never make live network requests.
"""

import hashlib
import hmac
import sys
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config import get_settings
from app.core.encryption import encrypt_credentials
from app.core.exceptions import PaymentError, ValidationError
from app.models.merchant import Merchant
from app.models.order import Order
from app.models.payment import Payment
from app.schemas.payment import RazorpayOrderResponse
from app.services.payment import PaymentService


class TestRazorpaySdkAndService:
    @pytest.fixture
    def merchant_id(self):
        return uuid.uuid4()

    @pytest.fixture
    def order_id(self):
        return uuid.uuid4()

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        return db

    def test_razorpay_sdk_initialization_without_pkg_resources(self):
        """
        Verify Razorpay SDK initializes cleanly even when pkg_resources is absent
        (as is standard on Python 3.12 without setuptools bundled).
        """
        orig_pkg_resources = sys.modules.get("pkg_resources")
        try:
            # Explicitly simulate missing pkg_resources
            sys.modules["pkg_resources"] = None

            import razorpay
            client = razorpay.Client(auth=("rzp_test_sample", "sample_secret_key"))
            assert client is not None
            assert hasattr(client, "order")
            assert hasattr(client.order, "create")
            assert hasattr(client, "utility")
            assert hasattr(client.utility, "verify_payment_signature")
        finally:
            if orig_pkg_resources is not None:
                sys.modules["pkg_resources"] = orig_pkg_resources
            else:
                sys.modules.pop("pkg_resources", None)

    @pytest.mark.asyncio
    async def test_initiate_success_with_mocked_order_create(self, mock_db, merchant_id, order_id):
        """
        Verify successful payment initiation with mocked client.order.create:
        - creates payment with pending status
        - creates outbox event
        - returns RazorpayOrderResponse
        - does NOT mark order as paid
        """
        order = Order(
            id=order_id,
            merchant_id=merchant_id,
            order_number="ORD-1001",
            total=Decimal("499.00"),
            currency="INR",
            status="pending",
        )
        merchant = Merchant(
            id=merchant_id,
            name="Test Boutique",
            slug="test-boutique",
            settings={},
        )

        # Mock database queries: Order, Merchant, existing Payment check
        mock_execute = AsyncMock()
        def db_query_side_effect(stmt):
            res = MagicMock()
            s = str(stmt)
            if "FROM orders" in s:
                res.scalar_one_or_none.return_value = order
            elif "FROM merchants" in s:
                res.scalar_one_or_none.return_value = merchant
            elif "FROM payments" in s:
                res.scalar_one_or_none.return_value = None
            return res

        mock_execute.side_effect = db_query_side_effect
        mock_db.execute = mock_execute

        mock_rz_order = {
            "id": "order_rzp_mock_123",
            "amount": 49900,
            "currency": "INR",
            "status": "created",
        }

        with patch("app.services.payment.get_settings") as mock_settings:
            settings_obj = MagicMock()
            settings_obj.razorpay_key_id = "rzp_test_default_key"
            settings_obj.razorpay_key_secret = "default_secret"
            mock_settings.return_value = settings_obj

            with patch("razorpay.Client") as MockClient:
                client_instance = MagicMock()
                client_instance.order.create.return_value = mock_rz_order
                MockClient.return_value = client_instance

                service = PaymentService(mock_db)
                response = await service.initiate(merchant_id, order_id)

                # Verify client auth
                MockClient.assert_called_once_with(auth=("rzp_test_default_key", "default_secret"))

                # Verify order creation payload
                client_instance.order.create.assert_called_once_with({
                    "amount": 49900,
                    "currency": "INR",
                    "receipt": "ORD-1001",
                })

                # Verify response
                assert isinstance(response, RazorpayOrderResponse)
                assert response.razorpay_order_id == "order_rzp_mock_123"
                assert response.amount == 49900
                assert response.currency == "INR"
                assert response.order_number == "ORD-1001"
                assert response.merchant_name == "Test Boutique"

                # Verify order status was NOT changed to paid/confirmed
                assert order.status == "pending"

                # Verify Payment record added
                assert mock_db.add.call_count == 2  # Payment + OutboxEvent
                payment_arg = mock_db.add.call_args_list[0][0][0]
                assert isinstance(payment_arg, Payment)
                assert payment_arg.status == "pending"
                assert payment_arg.provider_order_id == "order_rzp_mock_123"
                assert payment_arg.idempotency_key is not None

    @pytest.mark.asyncio
    async def test_initiate_retry_returns_existing_payment_without_duplicate(
        self, mock_db, merchant_id, order_id
    ):
        """
        Verify retrying initiate on an order that already has a pending payment
        returns the existing Razorpay order details instead of creating a duplicate payment.
        """
        order = Order(
            id=order_id,
            merchant_id=merchant_id,
            order_number="ORD-1002",
            total=Decimal("250.00"),
            currency="INR",
            status="pending",
        )
        merchant = Merchant(
            id=merchant_id,
            name="Test Boutique",
            slug="test-boutique",
            settings={},
        )
        existing_payment = Payment(
            id=uuid.uuid4(),
            order_id=order_id,
            merchant_id=merchant_id,
            amount=Decimal("250.00"),
            currency="INR",
            status="pending",
            provider="razorpay",
            provider_order_id="order_rzp_existing_456",
            idempotency_key=f"pay_{order_id}",
            created_at=datetime.now(timezone.utc),
        )

        mock_execute = AsyncMock()
        def db_query_side_effect(stmt):
            res = MagicMock()
            s = str(stmt)
            if "FROM orders" in s:
                res.scalar_one_or_none.return_value = order
            elif "FROM merchants" in s:
                res.scalar_one_or_none.return_value = merchant
            elif "FROM payments" in s:
                res.scalar_one_or_none.return_value = existing_payment
            return res

        mock_execute.side_effect = db_query_side_effect
        mock_db.execute = mock_execute

        with patch("razorpay.Client") as MockClient:
            service = PaymentService(mock_db)
            response = await service.initiate(merchant_id, order_id)

            # Client.order.create should NOT be called again
            MockClient.assert_not_called()

            # No new payment should be added
            mock_db.add.assert_not_called()

            assert response.razorpay_order_id == "order_rzp_existing_456"
            assert response.payment_id == existing_payment.id
            assert response.amount == 25000

    @pytest.mark.asyncio
    async def test_initiate_failure_sanitizes_errors_and_does_not_mark_paid(
        self, mock_db, merchant_id, order_id
    ):
        """
        Verify that when client.order.create fails:
        - Safe customer error is raised without exposing internal Python module names or tracebacks
        - Preserves useful error identifier (PAY-ERR-)
        - Order is NOT marked as paid
        - No payment record is committed to the database
        """
        order = Order(
            id=order_id,
            merchant_id=merchant_id,
            order_number="ORD-1003",
            total=Decimal("799.00"),
            currency="INR",
            status="pending",
        )
        merchant = Merchant(
            id=merchant_id,
            name="Test Boutique",
            slug="test-boutique",
            settings={},
        )

        mock_execute = AsyncMock()
        def db_query_side_effect(stmt):
            res = MagicMock()
            s = str(stmt)
            if "FROM orders" in s:
                res.scalar_one_or_none.return_value = order
            elif "FROM merchants" in s:
                res.scalar_one_or_none.return_value = merchant
            elif "FROM payments" in s:
                res.scalar_one_or_none.return_value = None
            return res

        mock_execute.side_effect = db_query_side_effect
        mock_db.execute = mock_execute

        with patch("app.services.payment.get_settings") as mock_settings:
            settings_obj = MagicMock()
            settings_obj.razorpay_key_id = "rzp_test_sample"
            settings_obj.razorpay_key_secret = "sample_secret"
            mock_settings.return_value = settings_obj

            with patch("razorpay.Client") as MockClient:
                client_instance = MagicMock()
                # Simulate a provider failure with internal traceback/module error
                client_instance.order.create.side_effect = ModuleNotFoundError(
                    "No module named 'pkg_resources'"
                )
                MockClient.return_value = client_instance

                service = PaymentService(mock_db)

                with pytest.raises(PaymentError) as exc_info:
                    await service.initiate(merchant_id, order_id)

                err_msg = str(exc_info.value)
                # Verify Python module names and tracebacks are NOT leaked
                assert "pkg_resources" not in err_msg
                assert "ModuleNotFoundError" not in err_msg
                assert "Traceback" not in err_msg
                assert "sample_secret" not in err_msg

                # Verify clean message with error reference
                assert "Payment provider unavailable" in err_msg
                assert "PAY-ERR-" in err_msg

                # Verify order is not marked paid
                assert order.status == "pending"

                # Verify no payment was added or committed
                mock_db.add.assert_not_called()
                mock_db.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_initiate_with_encrypted_merchant_credentials(
        self, mock_db, merchant_id, order_id
    ):
        """
        Verify existing merchant-specific encrypted credentials are properly decrypted
        and passed to the Razorpay SDK client.
        """
        encrypted_secret = encrypt_credentials({"secret": "merchant_custom_secret_777"})
        merchant = Merchant(
            id=merchant_id,
            name="Custom Merchant",
            slug="custom-merchant",
            settings={
                "payment_config": {
                    "razorpay_key_id": "rzp_test_merchant_custom_key",
                    "razorpay_key_secret": encrypted_secret,
                }
            },
        )
        order = Order(
            id=order_id,
            merchant_id=merchant_id,
            order_number="ORD-1004",
            total=Decimal("150.00"),
            currency="INR",
            status="pending",
        )

        mock_execute = AsyncMock()
        def db_query_side_effect(stmt):
            res = MagicMock()
            s = str(stmt)
            if "FROM orders" in s:
                res.scalar_one_or_none.return_value = order
            elif "FROM merchants" in s:
                res.scalar_one_or_none.return_value = merchant
            elif "FROM payments" in s:
                res.scalar_one_or_none.return_value = None
            return res

        mock_execute.side_effect = db_query_side_effect
        mock_db.execute = mock_execute

        with patch("razorpay.Client") as MockClient:
            client_instance = MagicMock()
            client_instance.order.create.return_value = {
                "id": "order_custom_999",
                "amount": 15000,
                "currency": "INR",
            }
            MockClient.return_value = client_instance

            service = PaymentService(mock_db)
            response = await service.initiate(merchant_id, order_id)

            # Verify client was initialized with merchant's specific decrypted secret
            MockClient.assert_called_once_with(
                auth=("rzp_test_merchant_custom_key", "merchant_custom_secret_777")
            )
            assert response.razorpay_key_id == "rzp_test_merchant_custom_key"
            assert response.razorpay_order_id == "order_custom_999"

    @pytest.mark.asyncio
    async def test_verify_checkout_hmac_sha256_success(self, mock_db, merchant_id, order_id):
        """
        Verify valid HMAC-SHA256 signature advances payment to captured
        and confirms order.
        """
        payment_id = uuid.uuid4()
        rz_order_id = "order_rzp_live_abc"
        rz_payment_id = "pay_rzp_live_xyz"
        secret = "test_verification_secret"

        # Calculate valid signature
        msg = f"{rz_order_id}|{rz_payment_id}".encode("utf-8")
        valid_signature = hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()

        payment = Payment(
            id=payment_id,
            order_id=order_id,
            merchant_id=merchant_id,
            amount=Decimal("300.00"),
            currency="INR",
            status="pending",
            provider="razorpay",
            provider_order_id=rz_order_id,
            idempotency_key="pay_idem_1",
            created_at=datetime.now(timezone.utc),
        )
        order = Order(
            id=order_id,
            merchant_id=merchant_id,
            order_number="ORD-1005",
            total=Decimal("300.00"),
            currency="INR",
            status="pending",
            items=[],
        )

        mock_execute = AsyncMock()
        def db_query_side_effect(stmt):
            res = MagicMock()
            s = str(stmt)
            if "FROM payments" in s or "JOIN orders" in s:
                res.first.return_value = (payment, order)
            elif "FROM merchants" in s:
                res.scalar_one_or_none.return_value = None
            return res

        mock_execute.side_effect = db_query_side_effect
        mock_db.execute = mock_execute

        with patch("app.services.payment.get_settings") as mock_settings:
            settings_obj = MagicMock()
            settings_obj.razorpay_key_secret = secret
            mock_settings.return_value = settings_obj

            with patch("app.services.inventory.InventoryService.confirm_sale", new_callable=AsyncMock):
                service = PaymentService(mock_db)
                result = await service.verify_checkout(
                    merchant_id=merchant_id,
                    payment_id=payment_id,
                    razorpay_order_id=rz_order_id,
                    razorpay_payment_id=rz_payment_id,
                    razorpay_signature=valid_signature,
                )

                assert result.status == "captured"
                assert payment.status == "captured"
                assert payment.provider_payment_id == rz_payment_id
                assert order.status == "confirmed"
                assert mock_db.commit.called

    @pytest.mark.asyncio
    async def test_verify_checkout_hmac_sha256_invalid_signature_fails(
        self, mock_db, merchant_id, order_id
    ):
        """
        Verify invalid HMAC-SHA256 signature marks payment failed and raises safe PaymentError.
        """
        payment_id = uuid.uuid4()
        rz_order_id = "order_rzp_live_abc"
        rz_payment_id = "pay_rzp_live_xyz"
        secret = "test_verification_secret"

        payment = Payment(
            id=payment_id,
            order_id=order_id,
            merchant_id=merchant_id,
            amount=Decimal("300.00"),
            currency="INR",
            status="pending",
            provider="razorpay",
            provider_order_id=rz_order_id,
            idempotency_key="pay_idem_2",
            created_at=datetime.now(timezone.utc),
        )
        order = Order(
            id=order_id,
            merchant_id=merchant_id,
            order_number="ORD-1006",
            total=Decimal("300.00"),
            currency="INR",
            status="pending",
            items=[],
        )

        mock_execute = AsyncMock()
        def db_query_side_effect(stmt):
            res = MagicMock()
            s = str(stmt)
            if "FROM payments" in s or "JOIN orders" in s:
                res.first.return_value = (payment, order)
            elif "FROM merchants" in s:
                res.scalar_one_or_none.return_value = None
            return res

        mock_execute.side_effect = db_query_side_effect
        mock_db.execute = mock_execute

        with patch("app.services.payment.get_settings") as mock_settings:
            settings_obj = MagicMock()
            settings_obj.razorpay_key_secret = secret
            mock_settings.return_value = settings_obj

            service = PaymentService(mock_db)
            with pytest.raises(PaymentError) as exc_info:
                await service.verify_checkout(
                    merchant_id=merchant_id,
                    payment_id=payment_id,
                    razorpay_order_id=rz_order_id,
                    razorpay_payment_id=rz_payment_id,
                    razorpay_signature="tampered_invalid_signature",
                )

            assert "Untrusted checkout" in str(exc_info.value)
            assert payment.status == "failed"
            assert payment.failure_reason == "Signature verification failed"
            assert order.status == "pending"  # Order not confirmed
