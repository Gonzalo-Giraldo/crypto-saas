from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, select
from datetime import datetime, timezone
from typing import Optional
import math

from apps.api.app.models.daily_risk import DailyRiskState
from apps.api.app.db.session import get_db
from apps.api.app.models.signal import Signal
from apps.api.app.models.position import Position
from apps.api.app.schemas.position import PositionOut
from apps.api.app.core.time import today_colombia
from apps.api.app.api.deps import get_current_user
from apps.api.app.models.user import User
from apps.api.app.models.user_risk_settings import UserRiskSettings
from apps.api.app.core.config import settings
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
from apps.api.app.services.state_machine import (
    assert_position_transition,
    assert_signal_transition,
    can_transition_signal,
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


def _capital_base_usd_for_user(db: Session, user_id: str) -> float:
    row = db.execute(
        select(UserRiskSettings).where(UserRiskSettings.user_id == user_id)
    ).scalar_one_or_none()
    if row and row.capital_base_usd and float(row.capital_base_usd) > 0:
        return float(row.capital_base_usd)
    return float(settings.DEFAULT_CAPITAL_BASE_USD)


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

    stop_required = bool(profile.get("stop_loss_required", True))
    if stop_required and s.stop_loss is None:
        _log_and_raise_risk_block(
            db=db,
            current_user=current_user,
            detail="Risk block: stop_loss is required by risk profile",
            action="position.open.blocked.stop_loss_required",
            extra={"profile_name": profile["profile_name"]},
        )

    if s.stop_loss is not None:
        entry_price = float(s.entry_price)
        stop_loss = float(s.stop_loss)
        risk_per_unit = abs(entry_price - stop_loss)
        if risk_per_unit <= 0:
            _log_and_raise_risk_block(
                db=db,
                current_user=current_user,
                detail="Risk block: invalid stop_loss distance",
                action="position.open.blocked.risk_per_trade.invalid_stop",
                extra={"entry_price": entry_price, "stop_loss": stop_loss},
            )

        capital_base_usd = _capital_base_usd_for_user(db, current_user.id)
        max_risk_per_trade_pct = float(profile["max_risk_per_trade_pct"])
        max_risk_amount = capital_base_usd * (max_risk_per_trade_pct / 100.0)
        requested_risk_amount = risk_per_unit * float(qty)

        if requested_risk_amount > max_risk_amount:
            max_qty_allowed = max_risk_amount / risk_per_unit if risk_per_unit > 0 else 0.0
            _log_and_raise_risk_block(
                db=db,
                current_user=current_user,
                detail=(
                    "Risk block: risk per trade exceeded "
                    f"(requested={round(requested_risk_amount, 6)} > max={round(max_risk_amount, 6)})"
                ),
                action="position.open.blocked.risk_per_trade",
                extra={
                    "capital_base_usd": capital_base_usd,
                    "max_risk_per_trade_pct": max_risk_per_trade_pct,
                    "max_risk_amount_usd": round(max_risk_amount, 6),
                    "requested_risk_amount_usd": round(requested_risk_amount, 6),
                    "risk_per_unit": round(risk_per_unit, 6),
                    "max_qty_allowed": round(max_qty_allowed, 6),
                },
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
    assert_signal_transition(s.status, "OPENED")
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
    idempotency_key: Optional[str] = Header(default=None, alias="X-Idempotency-Key"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    req_payload = {
        "position_id": position_id,
        "exit_price": float(exit_price),
        "fees": float(fees),
    }
    cached = consume_idempotent_response(
        db,
        user_id=current_user.id,
        endpoint="/positions/close",
        idempotency_key=idempotency_key,
        request_payload=req_payload,
    )
    if cached is not None:
        return cached

    if (not math.isfinite(float(exit_price))) or float(exit_price) <= 0:
        raise HTTPException(status_code=400, detail="exit_price must be finite and > 0")
    if (not math.isfinite(float(fees))) or float(fees) < 0:
        raise HTTPException(status_code=400, detail="fees must be finite and >= 0")

    profile = resolve_risk_profile(db, current_user.id, current_user.email)
    p = db.execute(select(Position).where(Position.id == position_id)).scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Position not found")
    if p.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Cannot close another user's position")

    assert_position_transition(p.status, "CLOSED")

    # PnL simple (LONG)
    realized_pnl = (float(exit_price) - float(p.entry_price)) * float(p.qty) - float(fees)

    p.fees = float(fees)
    p.realized_pnl = float(realized_pnl)
    p.status = "CLOSED"

    p.closed_at = datetime.now(timezone.utc)

    # marcar signal como COMPLETED
    s = db.execute(select(Signal).where(Signal.id == p.signal_id)).scalar_one_or_none()
    if s and can_transition_signal(s.status, "COMPLETED"):
        assert_signal_transition(s.status, "COMPLETED")
        s.status = "COMPLETED"
    elif s:
        log_audit_event(
            db,
            action="signal.transition.skipped",
            user_id=current_user.id,
            entity_type="signal",
            entity_id=s.id,
            details={"current_status": s.status, "target_status": "COMPLETED"},
        )

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
    store_idempotent_response(
        db,
        user_id=current_user.id,
        endpoint="/positions/close",
        idempotency_key=idempotency_key,
        request_payload=req_payload,
        response_payload=PositionOut.model_validate(p).model_dump(),
    )
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
        capital_base_usd = _capital_base_usd_for_user(db, current_user.id)
        max_risk_per_trade_pct = float(profile["max_risk_per_trade_pct"])
        return {
            "user_id": current_user.id,
            "day": str(today),
            "risk_profile": profile["profile_name"],
            "capital_base_usd": capital_base_usd,
            "max_risk_per_trade_pct": max_risk_per_trade_pct,
            "max_risk_amount_usd": round(capital_base_usd * (max_risk_per_trade_pct / 100.0), 6),
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
    capital_base_usd = _capital_base_usd_for_user(db, current_user.id)
    max_risk_per_trade_pct = float(profile["max_risk_per_trade_pct"])

    return {
        "user_id": dr.user_id,
        "day": str(dr.day),
        "risk_profile": profile["profile_name"],
        "capital_base_usd": capital_base_usd,
        "max_risk_per_trade_pct": max_risk_per_trade_pct,
        "max_risk_amount_usd": round(capital_base_usd * (max_risk_per_trade_pct / 100.0), 6),
        "trades_today": dr.trades_today,
        "realized_pnl_today": dr.realized_pnl_today,
        "daily_stop": dr.daily_stop,
        "max_trades": dr.max_trades,
        "max_open_positions": int(profile["max_open_positions"]),
        "cooldown_between_trades_minutes": float(profile["cooldown_between_trades_minutes"]),
        "remaining_trades": dr.max_trades - dr.trades_today,
        "remaining_loss_buffer": dr.daily_stop - dr.realized_pnl_today,
    }
