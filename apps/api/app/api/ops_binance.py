from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from apps.api.app.api.deps import require_role
from apps.api.app.db.session import get_db
from apps.api.app.models.user import User
from apps.api.app.services.exchange_secrets import get_decrypted_exchange_secret
from apps.worker.app.engine.execution_runtime import (
    _classify_binance_reconciliation,
    _reconcile_binance_test_order_best_effort,
)


router = APIRouter(prefix="/ops/admin", tags=["ops-admin"])


@router.get("/binance/reconcile-order")
def reconcile_binance_order(
    symbol: str = Query(...),
    client_order_id: str = Query(...),
    account_id: str = Query("default"),
    market: str = Query("FUTURES"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    symbol_norm = str(symbol or "").upper().strip()
    client_order_id_norm = str(client_order_id or "").strip()
    market_norm = str(market or "FUTURES").upper().strip()

    if market_norm != "FUTURES":
        return {
            "success": False,
            "classification": "INVALID_INPUT",
            "error": "binance_reconcile_order_supports_futures_only",
            "symbol": symbol_norm,
            "client_order_id": client_order_id_norm,
            "account_id": str(account_id or "default"),
            "market": market_norm,
        }

    creds = get_decrypted_exchange_secret(
        db=db,
        user_id=str(current_user.id),
        exchange="BINANCE",
    )
    if not creds:
        return {
            "success": False,
            "classification": "MISSING_CREDENTIALS",
            "error": "Missing credentials for BINANCE",
            "symbol": symbol_norm,
            "client_order_id": client_order_id_norm,
            "account_id": str(account_id or "default"),
            "market": market_norm,
        }

    reconciliation = _reconcile_binance_test_order_best_effort(
        api_key=creds["api_key"],
        api_secret=creds["api_secret"],
        symbol=symbol_norm,
        client_order_id=client_order_id_norm,
        market=market_norm,
    )
    classification = _classify_binance_reconciliation(
        result=reconciliation.get("result"),
        error=reconciliation.get("error"),
    )

    return {
        "success": reconciliation.get("error") is None,
        "classification": classification,
        "symbol": symbol_norm,
        "client_order_id": client_order_id_norm,
        "account_id": str(account_id or "default"),
        "market": market_norm,
        "result": reconciliation.get("result"),
        "error": reconciliation.get("error"),
        "mutations": [],
    }
