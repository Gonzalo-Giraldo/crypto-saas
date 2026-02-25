import base64
import hashlib

from cryptography.fernet import Fernet

from apps.api.app.core.config import settings


def _fernet_from_settings() -> Fernet:
    # Accepts any ENCRYPTION_KEY string and derives a stable Fernet key.
    digest = hashlib.sha256(settings.ENCRYPTION_KEY.encode("utf-8")).digest()
    fernet_key = base64.urlsafe_b64encode(digest)
    return Fernet(fernet_key)


def encrypt_value(plain_text: str) -> str:
    f = _fernet_from_settings()
    token = f.encrypt(plain_text.encode("utf-8"))
    return token.decode("utf-8")


def decrypt_value(cipher_text: str) -> str:
    f = _fernet_from_settings()
    plain = f.decrypt(cipher_text.encode("utf-8"))
    return plain.decode("utf-8")
