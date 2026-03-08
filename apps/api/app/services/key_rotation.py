import base64
import hashlib
from typing import Optional

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
    *,
    new_version: str = "v2",
    batch_size: int = 200,
    canary_count: Optional[int] = None,
):
    old_f = _fernet_from_raw_key(old_key)
    new_f = _fernet_from_raw_key(new_key)
    version = str(new_version or "v2").strip() or "v2"
    size = max(10, min(int(batch_size or 200), 1000))
    canary_limit = None if canary_count is None else max(1, int(canary_count))

    scanned = 0
    updated = 0
    failed = 0
    batches = 0
    last_id: Optional[str] = None

    while True:
        remaining = None if canary_limit is None else max(0, canary_limit - scanned)
        if remaining == 0:
            break

        fetch_limit = size if remaining is None else min(size, remaining)
        q = select(ExchangeSecret).order_by(ExchangeSecret.id.asc()).limit(fetch_limit)
        if last_id:
            q = q.where(ExchangeSecret.id > last_id)
        rows = db.execute(q).scalars().all()
        if not rows:
            break

        batches += 1
        for row in rows:
            scanned += 1
            last_id = row.id
            try:
                plain_api_key = old_f.decrypt(row.api_key_encrypted.encode("utf-8")).decode("utf-8")
                plain_api_secret = old_f.decrypt(row.api_secret_encrypted.encode("utf-8")).decode("utf-8")
            except Exception:
                failed += 1
                continue

            if not dry_run:
                row.api_key_encrypted = new_f.encrypt(plain_api_key.encode("utf-8")).decode("utf-8")
                row.api_secret_encrypted = new_f.encrypt(plain_api_secret.encode("utf-8")).decode("utf-8")
                row.key_version = version
                updated += 1
            else:
                updated += 1

        if not dry_run:
            db.commit()

    return {
        "dry_run": bool(dry_run),
        "scanned": int(scanned),
        "updated": int(updated),
        "failed": int(failed),
        "batch_size": int(size),
        "batches": int(batches),
        "new_version": version,
        "canary_count": canary_limit,
    }
