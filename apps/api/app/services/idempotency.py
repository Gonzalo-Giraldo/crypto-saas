import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from apps.api.app.core.config import settings
from apps.api.app.models.idempotency_key import IdempotencyKey


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _canonical_payload(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def consume_idempotent_response(
    db: Session,
    *,
    user_id: str,
    endpoint: str,
    idempotency_key: Optional[str],
    request_payload: dict,
):
    if not idempotency_key:
        return None

    key = idempotency_key.strip()
    if not key:
        return None
    if len(key) > 128:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Idempotency key too long (max 128 chars)",
        )

    key_hash = _sha256(key)
    request_hash = _sha256(_canonical_payload(request_payload))

    row = (
        db.execute(
            select(IdempotencyKey).where(
                IdempotencyKey.user_id == user_id,
                IdempotencyKey.endpoint == endpoint,
                IdempotencyKey.key_hash == key_hash,
            )
        )
        .scalar_one_or_none()
    )
    if not row:
        return None
    if row.request_hash != request_hash:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Idempotency key already used with different payload",
        )
    return json.loads(row.response_json)


def store_idempotent_response(
    db: Session,
    *,
    user_id: str,
    endpoint: str,
    idempotency_key: Optional[str],
    request_payload: dict,
    response_payload: dict,
    status_code: int = 200,
):
    if not idempotency_key:
        return
    key = idempotency_key.strip()
    if not key:
        return

    key_hash = _sha256(key)
    request_hash = _sha256(_canonical_payload(request_payload))
    payload_json = json.dumps(response_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)

    row = IdempotencyKey(
        user_id=user_id,
        endpoint=endpoint,
        key_hash=key_hash,
        request_hash=request_hash,
        response_json=payload_json,
        status_code=status_code,
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = (
            db.execute(
                select(IdempotencyKey).where(
                    IdempotencyKey.user_id == user_id,
                    IdempotencyKey.endpoint == endpoint,
                    IdempotencyKey.key_hash == key_hash,
                )
            )
            .scalar_one_or_none()
        )
        if existing and existing.request_hash == request_hash:
            return
        raise


def cleanup_old_idempotency_keys(db: Session) -> int:
    max_days = max(1, int(settings.IDEMPOTENCY_KEY_MAX_AGE_DAYS))
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_days)
    result = db.execute(
        delete(IdempotencyKey).where(IdempotencyKey.created_at < cutoff)
    )
    db.commit()
    return int(result.rowcount or 0)
