from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.app.core.config import settings
from apps.api.app.models.position import Position
from apps.api.app.models.runtime_setting import RuntimeSetting
from apps.api.app.models.user import User
from apps.api.app.services.audit import log_audit_event

TRADING_ENABLED_KEY = "trading_enabled"


def infer_exchange_from_symbol(symbol: str) -> str:
    s = (symbol or "").upper()
    if s.endswith("USDT") or "/USDT" in s:
        return "BINANCE"
    return "IBKR"


def get_trading_enabled(db: Session) -> bool:
    row = db.execute(
        select(RuntimeSetting).where(RuntimeSetting.key == TRADING_ENABLED_KEY)
    ).scalar_one_or_none()
    if row is None or row.bool_value is None:
        return bool(settings.TRADING_ENABLED_DEFAULT)
    return bool(row.bool_value)


def set_trading_enabled(db: Session, *, enabled: bool):
    row = db.execute(
        select(RuntimeSetting).where(RuntimeSetting.key == TRADING_ENABLED_KEY)
    ).scalar_one_or_none()
    if row is None:
        row = RuntimeSetting(key=TRADING_ENABLED_KEY, bool_value=bool(enabled))
        db.add(row)
    else:
        row.bool_value = bool(enabled)
    db.flush()
    return row


def assert_trading_enabled(
    db: Session,
    *,
    current_user: User,
    action: str,
    exchange: str = "",
):
    if get_trading_enabled(db):
        return
    log_audit_event(
        db,
        action="execution.blocked.kill_switch",
        user_id=current_user.id,
        entity_type="execution",
        details={"action": action, "exchange": exchange},
    )
    db.commit()
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Trading is globally disabled by admin kill-switch",
    )


def assert_exposure_limits(
    db: Session,
    *,
    current_user: User,
    exchange: str,
    symbol: str,
    qty: float,
    price_estimate: float = 0.0,
):
    max_qty = float(settings.MAX_OPEN_QTY_PER_SYMBOL)
    max_notional_exchange = float(settings.MAX_OPEN_NOTIONAL_PER_EXCHANGE)

    open_positions = (
        db.execute(
            select(Position).where(
                Position.user_id == current_user.id,
                Position.status == "OPEN",
            )
        )
        .scalars()
        .all()
    )

    symbol_upper = symbol.upper()
    exchange_upper = exchange.upper()
    open_qty_symbol = 0.0
    open_notional_exchange = 0.0
    for p in open_positions:
        p_symbol = (p.symbol or "").upper()
        p_exchange = infer_exchange_from_symbol(p_symbol)
        if p_symbol == symbol_upper:
            open_qty_symbol += float(p.qty)
        if p_exchange == exchange_upper:
            open_notional_exchange += float(p.qty) * float(p.entry_price)

    projected_qty_symbol = open_qty_symbol + float(qty)
    if max_qty > 0 and projected_qty_symbol > max_qty:
        log_audit_event(
            db,
            action="execution.blocked.exposure.symbol_qty",
            user_id=current_user.id,
            entity_type="risk",
            details={
                "exchange": exchange_upper,
                "symbol": symbol_upper,
                "projected_qty": projected_qty_symbol,
                "max_qty_per_symbol": max_qty,
            },
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Risk block: symbol exposure exceeded ({projected_qty_symbol}>{max_qty})",
        )

    projected_notional_exchange = open_notional_exchange + (float(qty) * max(0.0, float(price_estimate)))
    if max_notional_exchange > 0 and projected_notional_exchange > max_notional_exchange:
        log_audit_event(
            db,
            action="execution.blocked.exposure.exchange_notional",
            user_id=current_user.id,
            entity_type="risk",
            details={
                "exchange": exchange_upper,
                "symbol": symbol_upper,
                "projected_notional_exchange": projected_notional_exchange,
                "max_open_notional_per_exchange": max_notional_exchange,
            },
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Risk block: exchange exposure exceeded ({projected_notional_exchange}>{max_notional_exchange})",
        )
