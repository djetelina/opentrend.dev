import base64
import hashlib
import logging

from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)


def _derive_key(encryption_key: str) -> bytes:
    digest = hashlib.sha256(encryption_key.encode()).digest()
    return base64.urlsafe_b64encode(digest)


def encrypt_token(token: str, encryption_key: str) -> str:
    f = Fernet(_derive_key(encryption_key))
    return f.encrypt(token.encode()).decode()


def decrypt_token(encrypted: str, encryption_key: str) -> str:
    f = Fernet(_derive_key(encryption_key))
    return f.decrypt(encrypted.encode()).decode()


def try_decrypt_token(encrypted: str | None, encryption_key: str) -> str | None:
    """Decrypt a token, returning None (with logging) on failure or missing input."""
    if not encrypted:
        return None
    try:
        return decrypt_token(encrypted, encryption_key)
    except Exception:
        logger.error("Failed to decrypt token — encryption key may have changed")
        return None
