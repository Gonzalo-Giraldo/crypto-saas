from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from apps.api.app.api.deps import require_role
from apps.api.app.db.session import get_db
from apps.api.app.models.user import User
from apps.api.app.services.exchange_secrets import get_decrypted_exchange_secret
from apps.api.app.services.intent_service import get_intent
from apps.worker.app.engine.minimal_execution_runtime import IntentConsumptionStore
from apps.worker.app.engine.broker_positions import get_binance_positions
from apps.api.app.services.trading_controls import get_trading_enabled

from apps.worker.app.engine.binance_client import query_order_status_by_order_id
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


@router.get("/binance/intent-reconciliation")
def reconcile_binance_intent(
    intent_id: str = Query(...),
    account_id: str = Query("default"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    intent = get_intent(db, intent_id)
    if intent is None:
        return {
            "success": False,
            "classification": "INTENT_NOT_FOUND",
            "intent_id": str(intent_id),
            "mutations": [],
        }

    if str(intent.broker).upper() != "BINANCE":
        return {
            "success": False,
            "classification": "INVALID_BROKER",
            "intent_id": str(intent_id),
            "broker": str(intent.broker),
            "mutations": [],
        }

    account_id_norm = str(account_id or intent.account_id or "default").strip()
    store = IntentConsumptionStore()
    record = store.get_consumption_record(
        user_id=str(intent.user_id),
        broker="BINANCE",
        intent_key=str(intent.intent_id),
        account_id=account_id_norm,
    )

    if not record.get("found"):
        return {
            "success": False,
            "classification": "CONSUMPTION_NOT_FOUND",
            "intent_id": str(intent.intent_id),
            "account_id": account_id_norm,
            "lifecycle_status": str(intent.lifecycle_status),
            "mutations": [],
        }

    execution_ref = record.get("broker_execution_id")
    symbol = record.get("symbol") or str(intent.symbol)
    market = str(record.get("market") or "FUTURES").upper().strip()

    if not execution_ref:
        return {
            "success": False,
            "classification": "EXECUTION_REF_MISSING",
            "intent_id": str(intent.intent_id),
            "account_id": account_id_norm,
            "symbol": symbol,
            "market": market,
            "lifecycle_status": str(intent.lifecycle_status),
            "consumption": record,
            "mutations": [],
        }

    if market != "FUTURES":
        return {
            "success": False,
            "classification": "INVALID_MARKET",
            "intent_id": str(intent.intent_id),
            "account_id": account_id_norm,
            "symbol": symbol,
            "market": market,
            "lifecycle_status": str(intent.lifecycle_status),
            "consumption": record,
            "error": "binance_intent_reconciliation_supports_futures_only",
            "mutations": [],
        }

    creds = get_decrypted_exchange_secret(
        db=db,
        user_id=str(intent.user_id),
        exchange="BINANCE",
    )
    if not creds:
        return {
            "success": False,
            "classification": "MISSING_CREDENTIALS",
            "intent_id": str(intent.intent_id),
            "account_id": account_id_norm,
            "symbol": symbol,
            "market": market,
            "lifecycle_status": str(intent.lifecycle_status),
            "consumption": record,
            "error": "Missing credentials for BINANCE",
            "mutations": [],
        }

    execution_ref_type = str(record.get("broker_execution_id_type") or "").strip()

    if execution_ref_type == "orderId":
        try:
            reconciliation = {
                "result": query_order_status_by_order_id(
                    api_key=creds["api_key"],
                    api_secret=creds["api_secret"],
                    symbol=symbol,
                    order_id=str(execution_ref),
                    market=market,
                ),
                "error": None,
            }
        except Exception as exc:
            reconciliation = {"result": None, "error": str(exc)}
    elif execution_ref_type in {"client_order_id", "clientOrderId", "origClientOrderId"}:
        reconciliation = _reconcile_binance_test_order_best_effort(
            api_key=creds["api_key"],
            api_secret=creds["api_secret"],
            symbol=symbol,
            client_order_id=str(execution_ref),
            market=market,
        )
    else:
        return {
            "success": False,
            "classification": "INVALID_EXECUTION_REF_TYPE",
            "intent_id": str(intent.intent_id),
            "account_id": account_id_norm,
            "symbol": symbol,
            "market": market,
            "lifecycle_status": str(intent.lifecycle_status),
            "execution_ref": str(execution_ref),
            "execution_ref_type": execution_ref_type,
            "consumption": record,
            "error": "unsupported_binance_execution_ref_type",
            "mutations": [],
        }

    classification = _classify_binance_reconciliation(
        result=reconciliation.get("result"),
        error=reconciliation.get("error"),
    )

    return {
        "success": reconciliation.get("error") is None,
        "classification": classification,
        "intent_id": str(intent.intent_id),
        "account_id": account_id_norm,
        "symbol": symbol,
        "market": market,
        "lifecycle_status": str(intent.lifecycle_status),
        "execution_ref": str(execution_ref),
        "execution_ref_type": execution_ref_type,
        "consumption": record,
        "result": reconciliation.get("result"),
        "error": reconciliation.get("error"),
        "mutations": [],
    }

@router.get("/binance/reconcile-position")
def reconcile_binance_position(
    symbol: str = Query(...),
    account_id: str = Query("default"),
    market: str = Query("FUTURES"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    symbol_norm = str(symbol or "").upper().strip()
    market_norm = str(market or "FUTURES").upper().strip()
    account_id_norm = str(account_id or "default").strip()

    if market_norm != "FUTURES":
        return {
            "success": False,
            "classification": "INVALID_MARKET",
            "symbol": symbol_norm,
            "account_id": account_id_norm,
            "market": market_norm,
            "error": "binance_position_reconciliation_supports_futures_only",
            "mutations": [],
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
            "symbol": symbol_norm,
            "account_id": account_id_norm,
            "market": market_norm,
            "error": "Missing credentials for BINANCE",
            "mutations": [],
        }

    try:
        positions = get_binance_positions(
            api_key=creds["api_key"],
            api_secret=creds["api_secret"],
        )
    except Exception as exc:
        return {
            "success": False,
            "classification": "POSITION_UNKNOWN",
            "symbol": symbol_norm,
            "account_id": account_id_norm,
            "market": market_norm,
            "error": str(exc),
            "mutations": [],
        }

    matched = None

    for position in positions:
        if str(position.get("symbol") or "").upper().strip() == symbol_norm:
            matched = position
            break

    if matched is None:
        return {
            "success": True,
            "classification": "NO_OPEN_POSITION",
            "symbol": symbol_norm,
            "account_id": account_id_norm,
            "market": market_norm,
            "position": None,
            "protected": "UNKNOWN",
            "mutations": [],
        }

    return {
        "success": True,
        "classification": "OPEN_POSITION",
        "symbol": symbol_norm,
        "account_id": account_id_norm,
        "market": market_norm,
        "position": matched,
        "protected": "UNKNOWN",
        "mutations": [],
    }

@router.get("/binance/close-preflight")
def binance_close_preflight(
    symbol: str = Query(...),
    account_id: str = Query("default"),
    market: str = Query("FUTURES"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    symbol_norm = str(symbol or "").upper().strip()
    account_id_norm = str(account_id or "default").strip()
    market_norm = str(market or "FUTURES").upper().strip()

    if market_norm != "FUTURES":
        return {
            "success": False,
            "classification": "INVALID_MARKET",
            "symbol": symbol_norm,
            "account_id": account_id_norm,
            "market": market_norm,
            "error": "binance_close_preflight_supports_futures_only",
            "mutations": [],
        }

    if not get_trading_enabled(db):
        return {
            "success": False,
            "classification": "TRADING_DISABLED",
            "symbol": symbol_norm,
            "account_id": account_id_norm,
            "market": market_norm,
            "error": "trading_enabled_required_for_close_preflight",
            "mutations": [],
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
            "symbol": symbol_norm,
            "account_id": account_id_norm,
            "market": market_norm,
            "error": "Missing credentials for BINANCE",
            "mutations": [],
        }

    try:
        positions = get_binance_positions(
            api_key=creds["api_key"],
            api_secret=creds["api_secret"],
        )
    except Exception as exc:
        return {
            "success": False,
            "classification": "POSITION_UNKNOWN",
            "symbol": symbol_norm,
            "account_id": account_id_norm,
            "market": market_norm,
            "error": str(exc),
            "mutations": [],
        }

    matches = [
        p for p in positions
        if str(p.get("symbol") or "").upper().strip() == symbol_norm
    ]

    if len(matches) == 0:
        return {
            "success": False,
            "classification": "NO_OPEN_POSITION",
            "symbol": symbol_norm,
            "account_id": account_id_norm,
            "market": market_norm,
            "position_detected": False,
            "protected": "UNKNOWN",
            "mutations": [],
        }

    if len(matches) > 1:
        return {
            "success": False,
            "classification": "AMBIGUOUS_POSITION",
            "symbol": symbol_norm,
            "account_id": account_id_norm,
            "market": market_norm,
            "positions": matches,
            "protected": "UNKNOWN",
            "mutations": [],
        }

    position = matches[0]
    side = str(position.get("side") or "").upper().strip()
    qty = position.get("qty")

    try:
        qty_value = float(qty)
    except Exception:
        return {
            "success": False,
            "classification": "INVALID_POSITION_QTY",
            "symbol": symbol_norm,
            "account_id": account_id_norm,
            "market": market_norm,
            "position": position,
            "protected": "UNKNOWN",
            "mutations": [],
        }

    if qty_value <= 0:
        return {
            "success": False,
            "classification": "INVALID_POSITION_QTY",
            "symbol": symbol_norm,
            "account_id": account_id_norm,
            "market": market_norm,
            "position": position,
            "protected": "UNKNOWN",
            "mutations": [],
        }

    if side == "BUY":
        close_side = "SELL"
    elif side == "SELL":
        close_side = "BUY"
    else:
        return {
            "success": False,
            "classification": "INVALID_POSITION_SIDE",
            "symbol": symbol_norm,
            "account_id": account_id_norm,
            "market": market_norm,
            "position": position,
            "protected": "UNKNOWN",
            "mutations": [],
        }

    return {
        "success": True,
        "classification": "READY_TO_CLOSE",
        "symbol": symbol_norm,
        "account_id": account_id_norm,
        "market": market_norm,
        "position_detected": True,
        "position": position,
        "close_side": close_side,
        "qty": str(qty),
        "reduce_only": True,
        "protected": "UNKNOWN",
        "mutations": [],
    }
