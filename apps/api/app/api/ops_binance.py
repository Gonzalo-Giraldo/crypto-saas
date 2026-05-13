from __future__ import annotations

from sqlalchemy.orm import Session


from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from typing import Optional
from pydantic import BaseModel, Field, field_validator

from apps.api.app.services.audit import log_audit_event
from apps.api.app.services.idempotency import (
    reserve_idempotent_intent,
    finalize_idempotent_intent,
)


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


class BinanceExecuteCloseRequest(BaseModel):
    symbol: str
    qty: float = Field(gt=0)
    account_id: str = "default"
    market: str = "FUTURES"
    confirm: bool = False
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

    @field_validator("account_id")
    @classmethod
    def validate_account_id(cls, value: str) -> str:
        account_id = str(value or "").strip()

        if not account_id:
            raise ValueError("account_id_required")

        return account_id

    @field_validator("market")
    @classmethod
    def validate_market(cls, value: str) -> str:
        market = str(value or "").upper().strip()

        if market != "FUTURES":
            raise ValueError("binance_execute_close_supports_futures_only")

        return market

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



def _resolve_binance_close_context(
    *,
    positions: list,
    symbol: str,
    requested_qty: float | None = None,
    account_id: str = "default",
    market: str = "FUTURES",
) -> dict:
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
            "error": "binance_close_context_supports_futures_only",
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
            "classification": "HEDGE_MODE_UNSUPPORTED",
            "symbol": symbol_norm,
            "account_id": account_id_norm,
            "market": market_norm,
            "positions": matches,
            "error": "multiple_position_legs_or_ambiguous_position_for_symbol",
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

    if requested_qty is not None and float(requested_qty) != qty_value:
        return {
            "success": False,
            "classification": "POSITION_QTY_MISMATCH",
            "symbol": symbol_norm,
            "account_id": account_id_norm,
            "market": market_norm,
            "requested_qty": str(requested_qty),
            "position_qty": str(qty_value),
            "position": position,
            "protected": "UNKNOWN",
            "mutations": [],
        }

    if side == "BUY":
        close_side = "SELL"
        position_direction = "LONG"
    elif side == "SELL":
        close_side = "BUY"
        position_direction = "SHORT"
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
        "position_direction": position_direction,
        "close_side": close_side,
        "qty": str(qty_value),
        "reduce_only": True,
        "protected": "UNKNOWN",
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

@router.post("/binance/execute-close")
def binance_execute_close(
    payload: BinanceExecuteCloseRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
    idempotency_key: Optional[str] = Header(default=None, alias="X-Idempotency-Key"),
):
    req_payload = payload.model_dump()

    if not str(idempotency_key or "").strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="idempotency_key_required_for_close_execution")

    cached = reserve_idempotent_intent(
        db,
        user_id=str(current_user.id),
        endpoint="/ops/admin/binance/execute-close",
        idempotency_key=str(idempotency_key),
        request_payload=req_payload,
    )
    if cached is not None:
        return cached

    if not payload.confirm or not payload.execution_authorized:
        response_payload = {
            "success": False,
            "classification": "EXPLICIT_CONFIRMATION_REQUIRED",
            "symbol": payload.symbol,
            "account_id": payload.account_id,
            "market": payload.market,
            "error": "confirm_true_and_execution_authorized_true_required",
            "mutations": [],
        }
    elif not get_trading_enabled(db):
        response_payload = {
            "success": False,
            "classification": "TRADING_DISABLED",
            "symbol": payload.symbol,
            "account_id": payload.account_id,
            "market": payload.market,
            "error": "trading_enabled_required_for_close_execution",
            "mutations": [],
        }
    else:
        creds = get_decrypted_exchange_secret(
            db=db,
            user_id=str(current_user.id),
            exchange="BINANCE",
        )
        if not creds:
            response_payload = {
                "success": False,
                "classification": "MISSING_CREDENTIALS",
                "symbol": payload.symbol,
                "account_id": payload.account_id,
                "market": payload.market,
                "error": "Missing credentials for BINANCE",
                "mutations": [],
            }
        else:
            try:
                positions = get_binance_positions(
                    api_key=creds["api_key"],
                    api_secret=creds["api_secret"],
                )
                close_context = _resolve_binance_close_context(
                    positions=positions,
                    symbol=payload.symbol,
                    requested_qty=payload.qty,
                    account_id=payload.account_id,
                    market=payload.market,
                )
            except Exception as exc:
                close_context = {
                    "success": False,
                    "classification": "POSITION_UNKNOWN",
                    "symbol": payload.symbol,
                    "account_id": payload.account_id,
                    "market": payload.market,
                    "error": str(exc),
                    "mutations": [],
                }

            if not close_context.get("success"):
                response_payload = close_context
            else:
                client_order_id = f"csclose_{str(idempotency_key).replace('-', '')[:28]}"
                response_payload = {
                    "success": False,
                    "classification": "EXECUTION_PIPELINE_READY",
                    "symbol": payload.symbol,
                    "account_id": payload.account_id,
                    "market": payload.market,
                    "position": close_context.get("position"),
                    "position_direction": close_context.get("position_direction"),
                    "close_side": close_context.get("close_side"),
                    "qty": close_context.get("qty"),
                    "order_type": "MARKET",
                    "reduce_only": True,
                    "client_order_id": client_order_id,
                    "error": "execute_close_send_order_not_enabled_yet",
                    "mutations": [],
                }

    log_audit_event(
        db,
        action="execution.binance.close.blocked",
        user_id=str(current_user.id),
        entity_type="execution",
        details=response_payload,
    )
    db.commit()

    finalize_idempotent_intent(
        db,
        user_id=str(current_user.id),
        endpoint="/ops/admin/binance/execute-close",
        idempotency_key=str(idempotency_key),
        request_payload=req_payload,
        response_payload=response_payload,
        status_code=200,
    )

    return response_payload
