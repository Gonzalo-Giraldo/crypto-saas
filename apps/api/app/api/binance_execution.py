from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from apps.api.app.api.deps import get_current_user
from apps.api.app.db.session import get_db
from apps.api.app.models.user import User
from apps.api.app.services.intent_draft import BinanceIntentDraft
from apps.api.app.services.intent_persistence import persist_binance_intent_from_draft


router = APIRouter(tags=["binance-execution"])

class BinanceIntentExecuteRequest(BaseModel):
    symbol: str
    side: str
    qty: float = Field(gt=0)
    entry_price: float = Field(gt=0)
    stop_loss: float = Field(gt=0)
    take_profit: float = Field(gt=0)
    account_id: str = "default"
    execute_real: bool = False
    execution_authorized: bool = False

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, value: str) -> str:
        symbol = str(value or "").upper().strip()
        if not symbol:
            raise ValueError("symbol_required")
        if not symbol.endswith("USDT"):
            raise ValueError("binance_symbol_must_end_with_USDT")
        return symbol

    @field_validator("side")
    @classmethod
    def validate_side(cls, value: str) -> str:
        side = str(value or "").upper().strip()
        if side not in {"BUY", "SELL"}:
            raise ValueError("side_must_be_BUY_or_SELL")
        return side

    @field_validator("account_id")
    @classmethod
    def validate_account_id(cls, value: str) -> str:
        account_id = str(value or "").strip()
        if not account_id:
            raise ValueError("account_id_required")
        return account_id

@router.post("/execution/binance/intent-execute")
def intent_execute_binance(
    payload: BinanceIntentExecuteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    idempotency_key: Optional[str] = Header(default=None, alias="X-Idempotency-Key"),
):
    if payload.execute_real and not payload.execution_authorized:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="real_execution_authorization_required",
        )

    if payload.execute_real and not str(idempotency_key or "").strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="idempotency_key_required_for_real_execution",
        )

    draft = BinanceIntentDraft(
        symbol=payload.symbol,
        side=payload.side,
        expected_qty=payload.qty,
        entry_price=payload.entry_price,
        stop_loss=payload.stop_loss,
        take_profit=payload.take_profit,
        risk_pct=0.0,
        risk_abs=0.0,
        risk_usdt=None,
        reward_risk_ratio=None,
        entry_price_reference=payload.entry_price,
        auto_pick_trace={
            "final_score": 0.0,
            "decision_reason": "manual_binance_execution_request",
            "evidence": {
                "source": "binance_execution_router",
                "execution_authorized": bool(payload.execution_authorized),
            },
        },
    )

    try:
        return persist_binance_intent_from_draft(
            draft=draft,
            db=db,
            user_id=str(current_user.id),
            current_user=current_user,
            account_id=payload.account_id,
            execute_real=payload.execute_real,
            execution_authorized=payload.execution_authorized,
            idempotency_key=idempotency_key,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
