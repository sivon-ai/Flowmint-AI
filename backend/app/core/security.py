"""
Security utilities — JWT token management and password hashing.

NEVER log or expose JWT secrets, password hashes, or tokens in responses.
"""

from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import get_settings

settings = get_settings()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a plain-text password using bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain-text password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.jwt_access_token_expire_minutes)
    )
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(data: dict) -> str:
    """Create a JWT refresh token."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.jwt_refresh_token_expire_days)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict | None:
    """Decode and validate a JWT token. Returns None on failure."""
    try:
        payload = jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
        return payload
    except JWTError:
        return None


SENSITIVE_KEYS = {
    "password", "secret", "token", "api_key", "authorization", "key_secret",
    "webhook_secret", "jwt_secret_key", "secret_key", "credentials"
}


def redact_sensitive_data(val: any) -> any:
    """Recursively scrub sensitive keys and tokens from data structures."""
    if isinstance(val, dict):
        sanitized = {}
        for k, v in val.items():
            if any(s in str(k).lower() for s in SENSITIVE_KEYS):
                sanitized[k] = "***REDACTED***"
            else:
                sanitized[k] = redact_sensitive_data(v)
        return sanitized
    elif isinstance(val, list):
        return [redact_sensitive_data(item) for item in val]
    return val
