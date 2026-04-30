from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from apps.api.app.api.deps import get_current_user
from apps.api.app.db.session import get_db
from apps.api.app.models.user import User
from apps.api.app.services.binance_position_summary_service import (
    get_binance_position_summary_from_fills,
)

router = APIRouter(prefix="/ops", tags=["binance"])


@router.get("/binance/position-summary")
def get_binance_position_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_binance_position_summary_from_fills(
        db=db,
        user_id=current_user.id,
    )
