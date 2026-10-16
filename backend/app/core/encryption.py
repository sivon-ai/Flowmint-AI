"""
Flowmint AI — Authenticated encryption for store connection credentials.

Uses cryptography.fernet.Fernet (AES-128-CBC + HMAC-SHA256 authenticated encryption).
Never returns or logs decrypted secrets in plain text.
"""

import base64
import hashlib
import json
import logging
from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings
from app.core.exceptions import ValidationError

logger = logging.getLogger(__name__)


def _get_fernet() -> Fernet:
    settings = get_settings()
    key = settings.store_encryption_key
    if not key:
        # Deterministic derivation from SECRET_KEY for local/test environments
        derived = hashlib.sha256(settings.secret_key.encode("utf-8")).digest()
        key = base64.urlsafe_b64encode(derived).decode("utf-8")
    elif len(key) != 44:
        # Ensure 32-byte urlsafe base64 key
        derived = hashlib.sha256(key.encode("utf-8")).digest()
        key = base64.urlsafe_b64encode(derived).decode("utf-8")
    return Fernet(key.encode("utf-8"))


def encrypt_credentials(data: dict) -> str:
    """Encrypt a dictionary of store credentials into a safe ciphertext string."""
    f = _get_fernet()
    raw = json.dumps(data).encode("utf-8")
    return f.encrypt(raw).decode("utf-8")


def decrypt_credentials(encrypted_text: str) -> dict:
    """Decrypt ciphertext into the original dictionary of credentials."""
    try:
        f = _get_fernet()
        raw = f.decrypt(encrypted_text.encode("utf-8"))
        return json.loads(raw.decode("utf-8"))
    except (InvalidToken, Exception) as e:
        logger.error("Failed to decrypt credentials: %s", type(e).__name__)
        raise ValidationError("Unable to decrypt stored credentials. Key rotation or invalid token.")
