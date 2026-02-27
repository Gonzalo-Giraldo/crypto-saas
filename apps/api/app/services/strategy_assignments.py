from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.app.models.strategy_assignment import StrategyAssignment

ALLOWED_EXCHANGES = {"BINANCE", "IBKR"}
ALLOWED_STRATEGIES = {"SWING_V1", "INTRADAY_V1"}
DEFAULT_STRATEGY = "SWING_V1"


def normalize_exchange(exchange: str) -> str:
    value = (exchange or "").upper().strip()
    if value not in ALLOWED_EXCHANGES:
        raise ValueError("exchange must be BINANCE or IBKR")
    return value


def normalize_strategy(strategy_id: str) -> str:
    value = (strategy_id or "").upper().strip()
    if value not in ALLOWED_STRATEGIES:
        raise ValueError("strategy_id must be SWING_V1 or INTRADAY_V1")
    return value


def upsert_strategy_assignment(
    db: Session,
    user_id: str,
    exchange: str,
    strategy_id: str,
    enabled: bool,
) -> StrategyAssignment:
    normalized_exchange = normalize_exchange(exchange)
    normalized_strategy = normalize_strategy(strategy_id)

    row = (
        db.execute(
            select(StrategyAssignment).where(
                StrategyAssignment.user_id == user_id,
                StrategyAssignment.exchange == normalized_exchange,
            )
        )
        .scalar_one_or_none()
    )
    if row:
        row.strategy_id = normalized_strategy
        row.enabled = bool(enabled)
        return row

    row = StrategyAssignment(
        user_id=user_id,
        exchange=normalized_exchange,
        strategy_id=normalized_strategy,
        enabled=bool(enabled),
    )
    db.add(row)
    return row


def resolve_strategy_for_user_exchange(
    db: Session,
    user_id: str,
    exchange: str,
) -> dict:
    normalized_exchange = normalize_exchange(exchange)
    row = (
        db.execute(
            select(StrategyAssignment).where(
                StrategyAssignment.user_id == user_id,
                StrategyAssignment.exchange == normalized_exchange,
            )
        )
        .scalar_one_or_none()
    )
    if not row:
        return {
            "exchange": normalized_exchange,
            "strategy_id": DEFAULT_STRATEGY,
            "enabled": True,
            "source": "default",
        }

    return {
        "exchange": row.exchange,
        "strategy_id": row.strategy_id,
        "enabled": bool(row.enabled),
        "source": "assignment",
    }


def is_exchange_enabled_for_user(
    db: Session,
    user_id: str,
    exchange: str,
) -> bool:
    data = resolve_strategy_for_user_exchange(
        db=db,
        user_id=user_id,
        exchange=exchange,
    )
    return bool(data["enabled"])
