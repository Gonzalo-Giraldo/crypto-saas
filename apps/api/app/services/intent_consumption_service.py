from sqlalchemy.orm import Session
from sqlalchemy import text

from apps.api.app.services.intent_service import get_intent, mark_intent_consumed


def _build_consumer(user_id: str, broker: str, account_id: str | None) -> str:
    acc = account_id if (account_id and str(account_id).strip()) else "no-account"
    return f"{user_id}:{broker}:{acc}"


def consume_intent(
    *,
    db: Session,
    intent_id: str,
    user_id: str,
    broker: str,
    account_id: str | None = None,
):
    intent = get_intent(db, intent_id)
    if not intent:
        raise ValueError("intent_not_found")

    if intent.lifecycle_status != "CREATED":
        raise ValueError(f"invalid_state_for_consumption:{intent.lifecycle_status}")

    consumer = _build_consumer(user_id, broker, account_id)

    existing = db.execute(
        text("""
            SELECT 1
            FROM intent_consumptions
            WHERE intent_id = :intent_id AND consumer = :consumer
            LIMIT 1
        """),
        {"intent_id": intent_id, "consumer": consumer},
    ).fetchone()

    if existing:
        updated = mark_intent_consumed(db, intent_id)
        return {
            "intent_id": intent_id,
            "consumer": consumer,
            "lifecycle_status": updated.lifecycle_status,
            "already_consumed": True,
        }

    db.execute(
        text("""
            INSERT INTO intent_consumptions (intent_id, consumer)
            VALUES (:intent_id, :consumer)
            ON CONFLICT (intent_id, consumer) DO NOTHING
        """),
        {"intent_id": intent_id, "consumer": consumer},
    )

    updated = mark_intent_consumed(db, intent_id)

    return {
        "intent_id": intent_id,
        "consumer": consumer,
        "lifecycle_status": updated.lifecycle_status,
        "already_consumed": False,
    }
