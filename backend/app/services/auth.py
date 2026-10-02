"""
Authentication service — registration, login, token management.

Registration creates both a Merchant and a User (owner) in a single transaction.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthenticationError, ConflictError
from app.core.security import create_access_token, create_refresh_token, hash_password, verify_password, decode_token
from app.models.merchant import Merchant
from app.models.user import User
from app.schemas.auth import RegisterRequest, LoginRequest, TokenResponse, UserResponse


def _slugify(name: str) -> str:
    """Generate a URL-safe slug from a name."""
    import re
    slug = name.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def register(self, data: RegisterRequest) -> TokenResponse:
        """Register a new merchant with an owner user."""
        # Check email uniqueness globally for merchants
        existing = await self.db.execute(
            select(Merchant).where(Merchant.email == data.email)
        )
        if existing.scalar_one_or_none():
            raise ConflictError(f"Email {data.email} is already registered")

        # Create merchant
        slug = _slugify(data.merchant_name)
        # Ensure slug uniqueness
        slug_check = await self.db.execute(
            select(Merchant).where(Merchant.slug == slug)
        )
        if slug_check.scalar_one_or_none():
            slug = f"{slug}-{uuid.uuid4().hex[:6]}"

        merchant = Merchant(
            name=data.merchant_name,
            slug=slug,
            email=data.email,
            status="active",
        )
        self.db.add(merchant)
        await self.db.flush()

        # Create owner user
        user = User(
            merchant_id=merchant.id,
            email=data.email,
            hashed_password=hash_password(data.password),
            full_name=data.full_name,
            role="owner",
            is_active=True,
        )
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)

        # Generate tokens
        token_data = {
            "sub": str(user.id),
            "merchant_id": str(merchant.id),
            "role": user.role,
        }
        return TokenResponse(
            access_token=create_access_token(token_data),
            refresh_token=create_refresh_token(token_data),
        )

    async def login(self, data: LoginRequest) -> TokenResponse:
        """Authenticate a user and return tokens."""
        result = await self.db.execute(
            select(User).where(User.email == data.email)
        )
        user = result.scalar_one_or_none()
        if not user or not verify_password(data.password, user.hashed_password):
            raise AuthenticationError("Invalid email or password")

        if not user.is_active:
            raise AuthenticationError("User account is inactive")

        token_data = {
            "sub": str(user.id),
            "merchant_id": str(user.merchant_id),
            "role": user.role,
        }
        return TokenResponse(
            access_token=create_access_token(token_data),
            refresh_token=create_refresh_token(token_data),
        )

    async def refresh_tokens(self, refresh_token: str) -> TokenResponse:
        """Refresh access token using a valid refresh token."""
        payload = decode_token(refresh_token)
        if not payload or payload.get("type") != "refresh":
            raise AuthenticationError("Invalid refresh token")

        # Verify user still exists and is active
        user_id = payload.get("sub")
        result = await self.db.execute(
            select(User).where(User.id == uuid.UUID(user_id), User.is_active == True)
        )
        user = result.scalar_one_or_none()
        if not user:
            raise AuthenticationError("User not found or inactive")

        token_data = {
            "sub": str(user.id),
            "merchant_id": str(user.merchant_id),
            "role": user.role,
        }
        return TokenResponse(
            access_token=create_access_token(token_data),
            refresh_token=create_refresh_token(token_data),
        )

    async def get_current_user(self, user_id: uuid.UUID) -> UserResponse:
        """Get user profile."""
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        if not user:
            raise AuthenticationError("User not found")
        return UserResponse.model_validate(user)
