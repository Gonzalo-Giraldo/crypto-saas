from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from datetime import datetime, timezone

from apps.api.app.models.daily_risk import DailyRiskState
from apps.api.app.db.session import get_db
from apps.api.app.models.signal import Signal
from apps.api.app.models.position import Position
from apps.api.app.schemas.position import PositionOut
from apps.api.app.core.time import today_colombia

router = APIRouter(prefix="/positions", tags=["positions"])


@router.post("/open_from_signal", response_model=PositionOut)
def open_from_signal(signal_id: str, qty: float, db: Session = Depends(get_db)):
    s = db.execute(select(Signal).where(Signal.id == signal_id)).scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="Signal not found")
    if s.status != "EXECUTING":
        raise HTTPException(status_code=409, detail=f"Signal status must be EXECUTING (got {s.status})")

    if s.entry_price is None:
        raise HTTPException(status_code=400, detail="Signal missing entry_price")

    # RISK RULE: solo 1 posición OPEN por usuario
    open_pos = db.execute(
        select(Position).where(Position.user_id == s.user_id, Position.status == "OPEN")
    ).scalar_one_or_none()

    if open_pos:
        raise HTTPException(status_code=409, detail="Risk block: already has an OPEN position")

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

    if dr:
        if dr.realized_pnl_today <= dr.daily_stop:
            raise HTTPException(status_code=409, detail="Risk block: daily stop reached")

        if dr.trades_today >= dr.max_trades:
            raise HTTPException(status_code=409, detail="Risk block: max trades reached")

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

    # avanzamos el estado de la señal
    s.status = "OPENED"

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


    db.commit()
    db.refresh(p)
    return p


@router.get("", response_model=list[PositionOut])
def list_positions(db: Session = Depends(get_db)):
    rows = db.execute(select(Position).order_by(Position.opened_at.desc())).scalars().all()
    return rows

@router.post("/close", response_model=PositionOut)
def close_position(position_id: str, exit_price: float, fees: float = 0.0, db: Session = Depends(get_db)):
    p = db.execute(select(Position).where(Position.id == position_id)).scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Position not found")

    if p.status != "OPEN":
        raise HTTPException(status_code=409, detail=f"Position status must be OPEN (got {p.status})")

    # PnL simple (LONG)
    realized_pnl = (float(exit_price) - float(p.entry_price)) * float(p.qty) - float(fees)

    p.fees = float(fees)
    p.realized_pnl = float(realized_pnl)

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

    dr.trades_today += 1
    dr.realized_pnl_today += realized_pnl

    db.commit()
    db.refresh(p)
    return p

@router.get("/risk/today")
def get_today_risk(user_id: str, db: Session = Depends(get_db)):
    from apps.api.app.models.daily_risk import DailyRiskState
    from apps.api.app.core.time import today_colombia
    today = today_colombia()

    dr = (
        db.execute(
            select(DailyRiskState).where(
                DailyRiskState.user_id == user_id,
                DailyRiskState.day == today,
            )
        )
        .scalar_one_or_none()
    )

    if not dr:
        return {
            "user_id": user_id,
            "day": str(today),
            "trades_today": 0,
            "realized_pnl_today": 0.0,
            "daily_stop": -5.0,
            "max_trades": 3,
            "remaining_trades": 3,
            "remaining_loss_buffer": -5.0,
        }

    return {
        "user_id": dr.user_id,
        "day": str(dr.day),
        "trades_today": dr.trades_today,
        "realized_pnl_today": dr.realized_pnl_today,
        "daily_stop": dr.daily_stop,
        "max_trades": dr.max_trades,
        "remaining_trades": dr.max_trades - dr.trades_today,
        "remaining_loss_buffer": dr.daily_stop - dr.realized_pnl_today,
    }
