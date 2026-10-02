"""
API dependencies — authentication, tenant context, database sessions.

These are injected into route handlers via FastAPI's Depends().
"""

import uuid

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token
from app.database import get_db

security_scheme = HTTPBearer()


class CurrentUser:
    """Authenticated user context injected into route handlers."""

    def __init__(self, user_id: uuid.UUID, merchant_id: uuid.UUID, role: str):
        self.user_id = user_id
        self.merchant_id = merchant_id
        self.role = role


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
) -> CurrentUser:
    """Decode JWT and return current user context."""
    payload = decode_token(credentials.credentials)
    if not payload or payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    try:
        return CurrentUser(
            user_id=uuid.UUID(payload["sub"]),
            merchant_id=uuid.UUID(payload["merchant_id"]),
            role=payload["role"],
        )
    except (KeyError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )


def require_role(*roles: str):
    """Dependency that enforces role-based access control."""

    async def _check_role(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{user.role}' does not have access. Required: {', '.join(roles)}",
            )
        return user

    return _check_role
