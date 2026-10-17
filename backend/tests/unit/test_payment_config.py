"""
Unit tests for Razorpay Payment Configuration management in PaymentService.

Tests:
- Reading payment config (masked key ID, honest configuration status)
- Switching from 'later' to 'razorpay_hosted'
- Retaining existing credentials when updating only the payment mode
- Never overwriting existing secrets with empty/None fields
- Ensuring default Test Mode is preserved and not switched to Live Mode automatically
- Encryption of newly supplied credentials
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.models.merchant import Merchant
from app.services.payment import PaymentService
from app.core.encryption import encrypt_credentials, decrypt_credentials


class TestPaymentConfigService:
    @pytest.fixture
    def merchant_id(self):
        return uuid.uuid4()

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        return db

    @pytest.mark.asyncio
    async def test_get_payment_config_with_saved_merchant_settings(self, mock_db, merchant_id):
        """Verify get_payment_config accurately returns masked key ID and configuration status."""
        merchant = Merchant(
            id=merchant_id,
            name="Test Merchant Store",
            slug="test-store",
            settings={
                "payment_config": {
                    "payment_mode": "later",
                    "razorpay_mode": "test",
                    "razorpay_key_id": "rzp_test_1234567890abcdef",
                    "razorpay_key_secret": encrypt_credentials({"secret": "secret_abc123"}),
                }
            },
        )

        mock_execute = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = merchant
        mock_execute.return_value = mock_result
        mock_db.execute = mock_execute

        service = PaymentService(db=mock_db)
        config = await service.get_payment_config(merchant_id)

        assert config["payment_mode"] == "later"
        assert config["razorpay_mode"] == "test"
        assert config["razorpay_configured"] is True
        # Verify key ID is masked and does not reveal full string
        assert config["razorpay_key_id"] == "rzp_test_1..."
        # Verify secrets are NOT present
        assert "razorpay_key_secret" not in config

    @pytest.mark.asyncio
    async def test_switch_from_later_to_razorpay_hosted_retains_credentials(self, mock_db, merchant_id):
        """
        Switching payment_mode from 'later' to 'razorpay_hosted' with empty/omitted
        credentials preserves existing stored keys without erasing them.
        """
        encrypted_secret = encrypt_credentials({"secret": "existing_secret_xyz"})
        merchant = Merchant(
            id=merchant_id,
            name="Test Merchant Store",
            slug="test-store",
            settings={
                "payment_config": {
                    "payment_mode": "later",
                    "razorpay_mode": "test",
                    "razorpay_key_id": "rzp_test_orig1234567",
                    "razorpay_key_secret": encrypted_secret,
                }
            },
        )

        mock_execute = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = merchant
        mock_execute.return_value = mock_result
        mock_db.execute = mock_execute

        service = PaymentService(db=mock_db)

        # Update payload: only payment_mode and razorpay_mode, with empty/None credentials
        update_data = {
            "payment_mode": "razorpay_hosted",
            "razorpay_mode": "test",
            "razorpay_key_id": None,
            "razorpay_key_secret": "",
        }

        updated_config = await service.update_payment_config(merchant_id, update_data)

        # 1. Payment mode is updated
        assert updated_config["payment_mode"] == "razorpay_hosted"
        # 2. Mode remains test mode (not switched to live)
        assert updated_config["razorpay_mode"] == "test"
        # 3. Gateway remains configured and active
        assert updated_config["razorpay_configured"] is True
        assert updated_config["razorpay_key_id"] == "rzp_test_o..."

        # 4. Verify merchant model settings preserved the secret
        saved_p_conf = merchant.settings["payment_config"]
        assert saved_p_conf["payment_mode"] == "razorpay_hosted"
        assert saved_p_conf["razorpay_key_id"] == "rzp_test_orig1234567"
        assert saved_p_conf["razorpay_key_secret"] == encrypted_secret
        assert decrypt_credentials(saved_p_conf["razorpay_key_secret"])["secret"] == "existing_secret_xyz"

    @pytest.mark.asyncio
    async def test_update_with_new_credentials_encrypts_secret(self, mock_db, merchant_id):
        """Supplying new credentials securely encrypts the secret and updates the key."""
        merchant = Merchant(
            id=merchant_id,
            name="Test Merchant Store",
            slug="test-store",
            settings={},
        )

        mock_execute = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = merchant
        mock_execute.return_value = mock_result
        mock_db.execute = mock_execute

        service = PaymentService(db=mock_db)

        update_data = {
            "payment_mode": "razorpay_hosted",
            "razorpay_mode": "test",
            "razorpay_key_id": "rzp_test_newkey9999",
            "razorpay_key_secret": "new_secret_token_888",
        }

        updated_config = await service.update_payment_config(merchant_id, update_data)

        assert updated_config["payment_mode"] == "razorpay_hosted"
        assert updated_config["razorpay_configured"] is True
        assert updated_config["razorpay_key_id"] == "rzp_test_n..."

        # Verify encryption in merchant settings
        saved_secret = merchant.settings["payment_config"]["razorpay_key_secret"]
        assert saved_secret != "new_secret_token_888"
        decrypted = decrypt_credentials(saved_secret)
        assert decrypted["secret"] == "new_secret_token_888"
