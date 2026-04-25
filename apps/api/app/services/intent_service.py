from sqlalchemy.orm import Session
from sqlalchemy.exc import NoResultFound
from apps.api.app.models.intent import Intent
from sqlalchemy import select, update
from datetime import datetime

ALLOWED_BROKERS = {"BINANCE", "IBKR"}
ALLOWED_SIDES = {"BUY", "SELL"}
ALLOWED_TRANSITIONS = {
    ("CREATED", "CONSUMED"),
    ("CONSUMED", "EXECUTED"),
    ("EXECUTED", "PARTIALLY_FILLED"),
    ("EXECUTED", "FILLED"),
    ("EXECUTED", "FAILED"),
    ("CONSUMED", "FAILED"),
    ("CREATED", "FAILED"),
    ("CREATED", "CANCELLED"),
    ("CONSUMED", "CANCELLED"),
    ("PARTIALLY_FILLED", "FILLED"),
}

def create_intent(
    db: Session,
    user_id: str,
    broker: str,
    account_id: str,
    symbol: str,
    side: str,
    expected_qty,
    order_type: str,
    source: str,
    entry_price=None,
    stop_loss=None,
    take_profit=None,
    strategy_id=None,
    risk_pct=None,
    risk_abs=None,
    policy_snapshot=None,
):
    if not user_id or not isinstance(user_id, str):
        raise ValueError("user_id is required and must be a string")
    if broker not in ALLOWED_BROKERS:
        raise ValueError("broker must be BINANCE or IBKR")
    if not account_id or not isinstance(account_id, str):
        raise ValueError("account_id is required and must be a string")
    if not symbol or not isinstance(symbol, str):
        raise ValueError("symbol is required and must be a string")

    symbol = symbol.upper()

    if side not in ALLOWED_SIDES:
        raise ValueError("side must be BUY or SELL")

    try:
        qty = float(expected_qty)
    except Exception:
        raise ValueError("expected_qty must be numeric")

    if qty <= 0:
        raise ValueError("expected_qty must be > 0")

    if not order_type or not isinstance(order_type, str):
        raise ValueError("order_type is required")

    if not source or not isinstance(source, str):
        raise ValueError("source is required")

    intent = Intent(
        user_id=user_id,
        broker=broker,
        account_id=account_id,
        symbol=symbol,
        side=side,
        expected_qty=qty,
        order_type=order_type,
        source=source,
        lifecycle_status="CREATED",

        entry_price=float(entry_price) if entry_price is not None else None,
        stop_loss=float(stop_loss) if stop_loss is not None else None,
        take_profit=float(take_profit) if take_profit is not None else None,

        strategy_id=str(strategy_id) if strategy_id is not None else None,
        risk_pct=float(risk_pct) if risk_pct is not None else None,
        risk_abs=float(risk_abs) if risk_abs is not None else None,
        policy_snapshot=policy_snapshot,
    )




    db.add(intent)
    db.commit()
    db.refresh(intent)
    return intent

def get_intent(db: Session, intent_id):
    stmt = select(Intent).where(Intent.intent_id == intent_id)
    return db.execute(stmt).scalar_one_or_none()

def assert_intent_exists(db: Session, intent_id):
    intent = get_intent(db, intent_id)
    if not intent:
        raise NoResultFound("Intent not found")
    return intent

def _transition_intent(db: Session, intent_id, new_status):
    intent = assert_intent_exists(db, intent_id)

    if (intent.lifecycle_status, new_status) not in ALLOWED_TRANSITIONS:
        raise ValueError(f"Invalid transition {intent.lifecycle_status} -> {new_status}")

    stmt = (
        update(Intent)
        .where(Intent.intent_id == intent_id)
        .values(lifecycle_status=new_status, updated_at=datetime.utcnow())
    )
    db.execute(stmt)
    db.commit()

    return get_intent(db, intent_id)

def mark_intent_consumed(db: Session, intent_id):
    return _transition_intent(db, intent_id, "CONSUMED")

def mark_intent_executed(db: Session, intent_id):
    return _transition_intent(db, intent_id, "EXECUTED")

def mark_intent_failed(db: Session, intent_id, reason=None):
    return _transition_intent(db, intent_id, "FAILED")

def mark_intent_filled(db: Session, intent_id):
    return _transition_intent(db, intent_id, "FILLED")

def mark_intent_cancelled(db: Session, intent_id):
    return _transition_intent(db, intent_id, "CANCELLED")
