from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import select

from apps.api.app.db.session import get_db
from apps.api.app.models.signal import Signal
from apps.api.app.schemas.signal import SignalCreate, SignalOut

from apps.api.app.api.deps import get_current_user
from apps.api.app.models.user import User


router = APIRouter(prefix="/signals", tags=["signals"])

@router.post("", response_model=SignalOut)
def create_signal(
    payload: SignalCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    signal = Signal(
        user_id=current_user.id,   # 👈 clave
        symbol=payload.symbol,
        module=payload.module,
        base_risk_percent=payload.base_risk_percent,
        entry_price=payload.entry_price,
        stop_loss=payload.stop_loss,
        take_profit=payload.take_profit,
    )

    db.add(signal)
    db.commit()
    db.refresh(signal)
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


@router.get("", response_model=list[SignalOut])
def list_signals(db: Session = Depends(get_db)):
    rows = db.execute(select(Signal).order_by(Signal.created_at.desc())).scalars().all()
    return rows

from sqlalchemy import update
from sqlalchemy.orm import Session
from typing import List


@router.post("/claim", response_model=List[SignalOut])
def claim_signals(user_id: str, limit: int = 10, db: Session = Depends(get_db)):




    # seleccionar señales disponibles
    rows = (
        db.query(Signal)
        .filter(Signal.status == "CREATED", Signal.user_id == user_id)
        .order_by(Signal.created_at.asc())
        .limit(limit)
        .all()
    )

    claimed = []

    for signal in rows:
        signal.status = "EXECUTING"
        claimed.append(signal)

    db.commit()

    return claimed

