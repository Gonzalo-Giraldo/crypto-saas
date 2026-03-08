import base64
import hashlib
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

from apps.api.app.core.config import settings


def _fernet_from_raw_key(raw_key: str) -> Fernet:
    digest = hashlib.sha256(raw_key.encode("utf-8")).digest()
    fernet_key = base64.urlsafe_b64encode(digest)
    return Fernet(fernet_key)


def _keyring() -> dict[str, Fernet]:
    ring: dict[str, Fernet] = {}
    active_version = str(settings.ENCRYPTION_KEY_VERSION or "v1").strip() or "v1"
    ring[active_version] = _fernet_from_raw_key(settings.ENCRYPTION_KEY)

    prev_key = str(settings.ENCRYPTION_KEY_PREVIOUS or "").strip()
    prev_ver = str(settings.ENCRYPTION_KEY_PREVIOUS_VERSION or "").strip()
    if prev_key and prev_ver and prev_ver not in ring:
        ring[prev_ver] = _fernet_from_raw_key(prev_key)
    return ring


def get_active_key_version() -> str:
    return str(settings.ENCRYPTION_KEY_VERSION or "v1").strip() or "v1"


def encrypt_value(plain_text: str, *, key_version: Optional[str] = None) -> str:
    version = str(key_version or get_active_key_version()).strip()
    ring = _keyring()
    if version not in ring:
        raise ValueError(f"Unknown encryption key version: {version}")
    token = ring[version].encrypt(str(plain_text).encode("utf-8"))
    return token.decode("utf-8")


def decrypt_value(cipher_text: str, *, key_version: Optional[str] = None) -> str:
    ring = _keyring()
    ordered_versions: list[str] = []
    requested = str(key_version or "").strip()
    if requested and requested in ring:
        ordered_versions.append(requested)
    ordered_versions.extend([v for v in ring.keys() if v not in ordered_versions])

    last_error: Optional[Exception] = None
    for version in ordered_versions:
        try:
            plain = ring[version].decrypt(str(cipher_text).encode("utf-8"))
            return plain.decode("utf-8")
        except InvalidToken as exc:
            last_error = exc
            continue
    raise ValueError("Unable to decrypt value with configured keyring") from last_error
