from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from apps.api.app.api.deps import require_role
from apps.api.app.db.session import get_db
from apps.api.app.models.user import User
from apps.api.app.schemas.security import TradingControlOut, TradingControlUpdateRequest
from apps.api.app.services.audit import log_audit_event
from apps.api.app.services.trading_controls import get_trading_enabled, set_trading_enabled


router = APIRouter(prefix="/ops/admin", tags=["ops-admin"])


@router.get("/trading-control", response_model=TradingControlOut)
def get_trading_control(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    return TradingControlOut(
        trading_enabled=get_trading_enabled(db),
        updated_by=str(current_user.email or current_user.id),
        reason=None,
    )


@router.post("/trading-control", response_model=TradingControlOut)
def update_trading_control(
    payload: TradingControlUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    reason = str(payload.reason or "").strip()
    if payload.trading_enabled is False and len(reason) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="reason is required when disabling trading",
        )

    row = set_trading_enabled(db, enabled=bool(payload.trading_enabled))
    log_audit_event(
        db,
        action="ops.admin.trading_control.update",
        user_id=current_user.id,
        entity_type="runtime_setting",
        entity_id=str(row.id),
        details={
            "trading_enabled": bool(payload.trading_enabled),
            "reason": reason or None,
        },
    )
    db.commit()

    return TradingControlOut(
        trading_enabled=bool(payload.trading_enabled),
        updated_by=str(current_user.email or current_user.id),
        reason=reason or None,
    )
