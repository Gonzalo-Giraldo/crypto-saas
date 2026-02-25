import base64
import hashlib

from cryptography.fernet import Fernet
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.app.models.exchange_secret import ExchangeSecret


def _fernet_from_raw_key(raw_key: str) -> Fernet:
    digest = hashlib.sha256(raw_key.encode("utf-8")).digest()
    fernet_key = base64.urlsafe_b64encode(digest)
    return Fernet(fernet_key)


def reencrypt_exchange_secrets(
    db: Session,
    old_key: str,
    new_key: str,
    dry_run: bool = True,
):
    old_f = _fernet_from_raw_key(old_key)
    new_f = _fernet_from_raw_key(new_key)

    rows = db.execute(select(ExchangeSecret)).scalars().all()
    scanned = len(rows)
    updated = 0

    for row in rows:
        plain_api_key = old_f.decrypt(row.api_key_encrypted.encode("utf-8")).decode("utf-8")
        plain_api_secret = old_f.decrypt(row.api_secret_encrypted.encode("utf-8")).decode("utf-8")

        if not dry_run:
            row.api_key_encrypted = new_f.encrypt(plain_api_key.encode("utf-8")).decode("utf-8")
            row.api_secret_encrypted = new_f.encrypt(plain_api_secret.encode("utf-8")).decode("utf-8")
        updated += 1

    if not dry_run:
        db.commit()

    return {"dry_run": dry_run, "scanned": scanned, "updated": updated}
