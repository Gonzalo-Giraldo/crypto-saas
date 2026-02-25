from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import select

from apps.api.app.db.session import get_db
from apps.api.app.models.signal import Signal
from apps.api.app.schemas.signal import SignalCreate, SignalOut

from apps.api.app.api.deps import get_current_user
from apps.api.app.models.user import User
from apps.api.app.services.audit import log_audit_event


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
    db.flush()
    log_audit_event(
        db,
        action="signal.create",
        user_id=current_user.id,
        entity_type="signal",
        entity_id=signal.id,
        details={"symbol": payload.symbol, "module": payload.module},
    )
    db.commit()
    db.refresh(signal)
    return signal


@router.get("", response_model=list[SignalOut])
def list_signals(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (
        db.execute(
            select(Signal)
            .where(Signal.user_id == current_user.id)
            .order_by(Signal.created_at.desc())
        )
        .scalars()
        .all()
    )
    return rows


@router.post("/claim", response_model=List[SignalOut])
def claim_signals(
    limit: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # seleccionar señales disponibles
    rows = (
        db.query(Signal)
        .filter(Signal.status == "CREATED", Signal.user_id == current_user.id)
        .order_by(Signal.created_at.asc())
        .limit(limit)
        .all()
    )

    claimed = []

    for signal in rows:
        signal.status = "EXECUTING"
        claimed.append(signal)

    log_audit_event(
        db,
        action="signal.claim",
        user_id=current_user.id,
        entity_type="signal_batch",
        details={"claimed_count": len(claimed), "limit": limit},
    )
    db.commit()

    return claimed
