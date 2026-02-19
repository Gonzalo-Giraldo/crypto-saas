from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import select

from apps.api.app.db.session import get_db
from apps.api.app.models.signal import Signal
from apps.api.app.schemas.signal import SignalCreate, SignalOut

router = APIRouter(prefix="/signals", tags=["signals"])


@router.post("", response_model=SignalOut)
def create_signal(payload: SignalCreate, db: Session = Depends(get_db)):
    s = Signal(
        user_id=payload.user_id,
        symbol=payload.symbol,
        module=payload.module,
        base_risk_percent=payload.base_risk_percent,
        entry_price=payload.entry_price,
        stop_loss=payload.stop_loss,
        take_profit=payload.take_profit,
        status="CREATED",
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


@router.get("", response_model=list[SignalOut])
def list_signals(db: Session = Depends(get_db)):
    rows = db.execute(select(Signal).order_by(Signal.created_at.desc())).scalars().all()
    return rows

