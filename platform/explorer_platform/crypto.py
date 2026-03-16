"""Fernet symmetric encryption for stored credentials."""

from cryptography.fernet import Fernet

from explorer_platform.config import FERNET_KEY

_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        if not FERNET_KEY:
            raise RuntimeError("PLATFORM_FERNET_KEY not set")
        _fernet = Fernet(FERNET_KEY.encode())
    return _fernet


def encrypt(plaintext: str) -> str:
    """Encrypt a string. Returns base64 ciphertext."""
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    """Decrypt base64 ciphertext. Returns plaintext string."""
    return _get_fernet().decrypt(ciphertext.encode()).decode()
