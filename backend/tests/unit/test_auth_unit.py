"""
Unit tests for Authentication and Role Authorization.

Tests:
- Password hashing with bcrypt and verification
- Incorrect password detection
- JWT access and refresh token generation and decoding
- Token expiration detection
- CurrentUser creation and payload validation
- Role verification with require_role (OWNER, ADMIN, VIEWER)
"""

import uuid
from datetime import timedelta

import pytest
from fastapi import HTTPException

from app.api.deps import CurrentUser, require_role
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


class TestAuthSecurityUnit:
    def test_password_hashing_and_verification(self):
        password = "supersecretpassword123"
        hashed = hash_password(password)
        assert hashed != password
        assert verify_password(password, hashed) is True
        assert verify_password("wrongpassword", hashed) is False

    def test_token_creation_and_decoding(self):
        user_id = uuid.uuid4()
        merchant_id = uuid.uuid4()
        token_data = {
            "sub": str(user_id),
            "merchant_id": str(merchant_id),
            "role": "owner",
        }
        access_token = create_access_token(token_data)
        payload = decode_token(access_token)

        assert payload is not None
        assert payload["sub"] == str(user_id)
        assert payload["merchant_id"] == str(merchant_id)
        assert payload["role"] == "owner"
        assert payload["type"] == "access"

    def test_refresh_token_type(self):
        user_id = uuid.uuid4()
        merchant_id = uuid.uuid4()
        token_data = {
            "sub": str(user_id),
            "merchant_id": str(merchant_id),
            "role": "admin",
        }
        refresh_token = create_refresh_token(token_data)
        payload = decode_token(refresh_token)

        assert payload is not None
        assert payload["type"] == "refresh"
        assert payload["sub"] == str(user_id)

    def test_expired_token_decoding(self):
        token_data = {"sub": "123", "role": "viewer"}
        expired_token = create_access_token(token_data, expires_delta=timedelta(seconds=-10))
        assert decode_token(expired_token) is None

    def test_invalid_token_decoding(self):
        assert decode_token("completely.invalid.token") is None
        assert decode_token("") is None

    @pytest.mark.asyncio
    async def test_require_role_allowed(self):
        user = CurrentUser(
            user_id=uuid.uuid4(),
            merchant_id=uuid.uuid4(),
            role="owner",
        )
        check_fn = require_role("owner", "admin")
        result = await check_fn(user)
        assert result.role == "owner"

    @pytest.mark.asyncio
    async def test_require_role_forbidden(self):
        user = CurrentUser(
            user_id=uuid.uuid4(),
            merchant_id=uuid.uuid4(),
            role="viewer",
        )
        check_fn = require_role("owner", "admin")
        with pytest.raises(HTTPException) as exc_info:
            await check_fn(user)
        assert exc_info.value.status_code == 403
        assert "viewer" in exc_info.value.detail
