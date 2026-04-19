from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from apps.api.app.db.session import get_db
from apps.api.app.api.deps import get_current_user
from apps.api.app.models.user import User
from apps.api.app.services.binance_ping import ping_binance_credentials
from apps.api.app.services.exchange_secrets import get_decrypted_exchange_secret

router = APIRouter(tags=["ops"])


@router.get("/ops/execution/binance/ping")
def execution_binance_ping(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    secret = get_decrypted_exchange_secret(db=db, user_id=current_user.id, exchange="BINANCE")
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="BINANCE secret not configured for current user",
        )
    api_key = secret.get("api_key")
    api_secret = secret.get("api_secret")
    if not api_key or not api_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="BINANCE secret is incomplete for current user",
        )
    return ping_binance_credentials(api_key=api_key, api_secret=api_secret)
