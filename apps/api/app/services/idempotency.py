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


def _parse_response_json(response_json: str) -> dict:
    try:
        return json.loads(response_json or "{}")
    except Exception:
        return {}


def reserve_idempotent_intent(
    db: Session,
    *,
    user_id: str,
    endpoint: str,
    idempotency_key: str,
    request_payload: dict,
) -> dict | None:
    if not idempotency_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Idempotency-Key is required",
        )
    key = str(idempotency_key or "").strip()
    if not key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Idempotency-Key is required",
        )
    if len(key) > 128:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Idempotency key too long (max 128 chars)",
        )

    key_hash = _sha256(key)
    request_hash = _sha256(_canonical_payload(request_payload))

    row = IdempotencyKey(
        user_id=user_id,
        endpoint=endpoint,
        key_hash=key_hash,
        request_hash=request_hash,
        response_json=json.dumps({"status": "in_progress"}),
        status_code=102,
    )
    db.add(row)
    try:
        db.commit()
        return None
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
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Idempotency reservation conflict",
            )
        if existing.request_hash != request_hash:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Idempotency key already used with different payload",
            )

        existing_data = _parse_response_json(existing.response_json)
        if existing_data.get("status") == "in_progress":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Auto-pick execution already in progress",
            )

        return existing_data


def finalize_idempotent_intent(
    db: Session,
    *,
    user_id: str,
    endpoint: str,
    idempotency_key: str,
    request_payload: dict,
    response_payload: dict,
    status_code: int = 200,
):
    if not idempotency_key:
        return
    key = str(idempotency_key or "").strip()
    if not key:
        return

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
    if row is None:
        row = IdempotencyKey(
            user_id=user_id,
            endpoint=endpoint,
            key_hash=key_hash,
            request_hash=request_hash,
            response_json=json.dumps(response_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True),
            status_code=status_code,
        )
        db.add(row)
        db.commit()
        return

    if row.request_hash != request_hash:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Idempotency key already used with different payload",
        )

    row.response_json = json.dumps(response_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    row.status_code = status_code
    db.commit()


def cleanup_old_idempotency_keys(db: Session) -> int:
    max_days = max(1, int(settings.IDEMPOTENCY_KEY_MAX_AGE_DAYS))
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_days)
    result = db.execute(
        delete(IdempotencyKey).where(IdempotencyKey.created_at < cutoff)
    )
    db.commit()
    return int(result.rowcount or 0)
