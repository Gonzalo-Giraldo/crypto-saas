from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.app.models.exchange_secret import ExchangeSecret
from apps.api.app.services.crypto import decrypt_value, encrypt_value


def upsert_exchange_secret(
    db: Session,
    user_id: str,
    exchange: str,
    api_key: str,
    api_secret: str,
) -> ExchangeSecret:
    normalized_exchange = exchange.upper()
    row = (
        db.execute(
            select(ExchangeSecret).where(
                ExchangeSecret.user_id == user_id,
                ExchangeSecret.exchange == normalized_exchange,
            )
        )
        .scalar_one_or_none()
    )

    encrypted_key = encrypt_value(api_key)
    encrypted_secret = encrypt_value(api_secret)

    if row:
        row.api_key_encrypted = encrypted_key
        row.api_secret_encrypted = encrypted_secret
        return row

    row = ExchangeSecret(
        user_id=user_id,
        exchange=normalized_exchange,
        api_key_encrypted=encrypted_key,
        api_secret_encrypted=encrypted_secret,
    )
    db.add(row)
    return row


def get_decrypted_exchange_secret(
    db: Session,
    user_id: str,
    exchange: str,
) -> Optional[dict[str, str]]:
    normalized_exchange = exchange.upper()
    row = (
        db.execute(
            select(ExchangeSecret).where(
                ExchangeSecret.user_id == user_id,
                ExchangeSecret.exchange == normalized_exchange,
            )
        )
        .scalar_one_or_none()
    )
    if not row:
        return None

    return {
        "exchange": row.exchange,
        "api_key": decrypt_value(row.api_key_encrypted),
        "api_secret": decrypt_value(row.api_secret_encrypted),
    }
