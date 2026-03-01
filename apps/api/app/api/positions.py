from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, select
from datetime import datetime, timezone
from typing import Optional

from apps.api.app.models.daily_risk import DailyRiskState
from apps.api.app.db.session import get_db
from apps.api.app.models.signal import Signal
from apps.api.app.models.position import Position
from apps.api.app.schemas.position import PositionOut
from apps.api.app.core.time import today_colombia
from apps.api.app.api.deps import get_current_user
from apps.api.app.models.user import User
from apps.api.app.services.audit import log_audit_event
from apps.api.app.services.risk_profiles import (
    apply_profile_daily_limits,
    resolve_risk_profile,
)
from apps.api.app.services.idempotency import (
    consume_idempotent_response,
    store_idempotent_response,
)
from apps.api.app.services.trading_controls import (
    assert_exposure_limits,
    assert_trading_enabled,
    infer_exchange_from_symbol,
)

router = APIRouter(prefix="/positions", tags=["positions"])


def _log_and_raise_risk_block(
    db: Session,
    current_user: User,
    detail: str,
    action: str,
    extra: Optional[dict] = None,
):
    log_audit_event(
        db,
        action=action,
        user_id=current_user.id,
        entity_type="risk",
        details=extra or {},
    )
    db.commit()
    raise HTTPException(status_code=409, detail=detail)


@router.post("/open_from_signal", response_model=PositionOut)
def open_from_signal(
    signal_id: str,
    qty: float,
    idempotency_key: Optional[str] = Header(default=None, alias="X-Idempotency-Key"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    req_payload = {"signal_id": signal_id, "qty": float(qty)}
    cached = consume_idempotent_response(
        db,
        user_id=current_user.id,
        endpoint="/positions/open_from_signal",
        idempotency_key=idempotency_key,
        request_payload=req_payload,
    )
    if cached is not None:
        return cached

    profile = resolve_risk_profile(db, current_user.id, current_user.email)
    s = db.execute(select(Signal).where(Signal.id == signal_id)).scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="Signal not found")
    if s.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Cannot open another user's signal")
    if s.status != "EXECUTING":
        raise HTTPException(status_code=409, detail=f"Signal status must be EXECUTING (got {s.status})")

    if s.entry_price is None:
        raise HTTPException(status_code=400, detail="Signal missing entry_price")

    inferred_exchange = infer_exchange_from_symbol(s.symbol)
    assert_trading_enabled(
        db=db,
        current_user=current_user,
        action="position_open",
        exchange=inferred_exchange,
    )
    assert_exposure_limits(
        db=db,
        current_user=current_user,
        exchange=inferred_exchange,
        symbol=s.symbol,
        qty=float(qty),
        price_estimate=float(s.entry_price),
    )

    open_positions = (
        db.execute(
            select(Position).where(Position.user_id == s.user_id, Position.status == "OPEN")
        )
        .scalars()
        .all()
    )

    if len(open_positions) >= int(profile["max_open_positions"]):
        _log_and_raise_risk_block(
            db=db,
            current_user=current_user,
            detail="Risk block: max open positions reached",
            action="position.open.blocked.max_open_positions",
            extra={"max_open_positions": profile["max_open_positions"]},
        )

    last_trade_at = db.execute(
        select(func.max(func.coalesce(Position.closed_at, Position.opened_at))).where(
            Position.user_id == s.user_id
        )
    ).scalar_one_or_none()
    if last_trade_at:
        if last_trade_at.tzinfo is None:
            last_trade_at = last_trade_at.replace(tzinfo=timezone.utc)
        elapsed_minutes = (datetime.now(timezone.utc) - last_trade_at.astimezone(timezone.utc)).total_seconds() / 60.0
        cooldown_minutes = float(profile["cooldown_between_trades_minutes"])
        if elapsed_minutes < cooldown_minutes:
            _log_and_raise_risk_block(
                db=db,
                current_user=current_user,
                detail=f"Risk block: cooldown active ({cooldown_minutes}m)",
                action="position.open.blocked.cooldown",
                extra={"cooldown_minutes": cooldown_minutes, "elapsed_minutes": round(elapsed_minutes, 2)},
            )

    today = today_colombia()

    dr = (
        db.execute(
            select(DailyRiskState).where(
                DailyRiskState.user_id == s.user_id,
                DailyRiskState.day == today,
            )
        )
        .scalar_one_or_none()
    )
    if not dr:
        dr = DailyRiskState(user_id=s.user_id, day=today)
        db.add(dr)
        db.flush()
    apply_profile_daily_limits(dr, profile)

    if dr.realized_pnl_today <= dr.daily_stop:
        _log_and_raise_risk_block(
            db=db,
            current_user=current_user,
            detail="Risk block: daily stop reached",
            action="position.open.blocked.daily_stop",
            extra={"realized_pnl_today": dr.realized_pnl_today, "daily_stop": dr.daily_stop},
        )

    if dr.trades_today >= dr.max_trades:
        _log_and_raise_risk_block(
            db=db,
            current_user=current_user,
            detail="Risk block: max trades reached",
            action="position.open.blocked.max_trades",
            extra={"trades_today": dr.trades_today, "max_trades": dr.max_trades},
        )

    p = Position(
        user_id=s.user_id,
        signal_id=s.id,
        symbol=s.symbol,
        side="LONG",
        qty=float(qty),
        entry_price=float(s.entry_price),
        stop_loss=s.stop_loss,
        take_profit=s.take_profit,
        status="OPEN",
    )
    db.add(p)
    db.flush()

    # avanzamos el estado de la señal
    s.status = "OPENED"

    log_audit_event(
        db,
        action="position.open",
        user_id=current_user.id,
        entity_type="position",
        entity_id=p.id,
        details={"signal_id": s.id, "symbol": p.symbol, "qty": p.qty},
    )

    db.commit()
    db.refresh(p)
    store_idempotent_response(
        db,
        user_id=current_user.id,
        endpoint="/positions/open_from_signal",
        idempotency_key=idempotency_key,
        request_payload=req_payload,
        response_payload=PositionOut.model_validate(p).model_dump(),
    )
    return p


@router.get("", response_model=list[PositionOut])
def list_positions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (
        db.execute(
            select(Position)
            .where(Position.user_id == current_user.id)
            .order_by(Position.opened_at.desc())
        )
        .scalars()
        .all()
    )
    return rows

@router.post("/close", response_model=PositionOut)
def close_position(
    position_id: str,
    exit_price: float,
    fees: float = 0.0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    profile = resolve_risk_profile(db, current_user.id, current_user.email)
    p = db.execute(select(Position).where(Position.id == position_id)).scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Position not found")
    if p.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Cannot close another user's position")

    if p.status != "OPEN":
        raise HTTPException(status_code=409, detail=f"Position status must be OPEN (got {p.status})")

    # PnL simple (LONG)
    realized_pnl = (float(exit_price) - float(p.entry_price)) * float(p.qty) - float(fees)

    p.fees = float(fees)
    p.realized_pnl = float(realized_pnl)
    p.status = "CLOSED"

    p.closed_at = datetime.now(timezone.utc)

    # marcar signal como COMPLETED
    s = db.execute(select(Signal).where(Signal.id == p.signal_id)).scalar_one_or_none()
    if s:
        s.status = "COMPLETED"

    today = today_colombia()

    dr = (
        db.execute(
            select(DailyRiskState).where(
                DailyRiskState.user_id == p.user_id,
                DailyRiskState.day == today,
            )
        )
        .scalar_one_or_none()
    )

    if not dr:
        dr = DailyRiskState(user_id=p.user_id, day=today)
        db.add(dr)
        db.flush()
    apply_profile_daily_limits(dr, profile)

    dr.trades_today += 1
    dr.realized_pnl_today += realized_pnl

    log_audit_event(
        db,
        action="position.close",
        user_id=current_user.id,
        entity_type="position",
        entity_id=p.id,
        details={"realized_pnl": realized_pnl, "fees": fees},
    )
    db.commit()
    db.refresh(p)
    return p

@router.get("/risk/today")
def get_today_risk(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    profile = resolve_risk_profile(db, current_user.id, current_user.email)
    today = today_colombia()

    dr = (
        db.execute(
            select(DailyRiskState).where(
                DailyRiskState.user_id == current_user.id,
                DailyRiskState.day == today,
            )
        )
        .scalar_one_or_none()
    )

    if not dr:
        daily_stop = -abs(float(profile["max_daily_loss_pct"]))
        max_trades = int(profile["max_trades_per_day"])
        return {
            "user_id": current_user.id,
            "day": str(today),
            "risk_profile": profile["profile_name"],
            "trades_today": 0,
            "realized_pnl_today": 0.0,
            "daily_stop": daily_stop,
            "max_trades": max_trades,
            "max_open_positions": int(profile["max_open_positions"]),
            "cooldown_between_trades_minutes": float(profile["cooldown_between_trades_minutes"]),
            "remaining_trades": max_trades,
            "remaining_loss_buffer": daily_stop,
        }

    apply_profile_daily_limits(dr, profile)
    db.commit()

    return {
        "user_id": dr.user_id,
        "day": str(dr.day),
        "risk_profile": profile["profile_name"],
        "trades_today": dr.trades_today,
        "realized_pnl_today": dr.realized_pnl_today,
        "daily_stop": dr.daily_stop,
        "max_trades": dr.max_trades,
        "max_open_positions": int(profile["max_open_positions"]),
        "cooldown_between_trades_minutes": float(profile["cooldown_between_trades_minutes"]),
        "remaining_trades": dr.max_trades - dr.trades_today,
        "remaining_loss_buffer": dr.daily_stop - dr.realized_pnl_today,
    }
