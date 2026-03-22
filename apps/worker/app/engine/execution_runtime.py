def cancel_broker_order(
    *,
    exchange: str,
    api_key: str = None,
    api_secret: str = None,
    symbol: str,
    client_order_id: str,
    market: str = "SPOT",
    user_id: str = None,
):
    """
    Cancel an order via the runtime, resolving the broker and credentials, and using the adapter abstraction.
    """
    db = SessionLocal()
    try:
        # If credentials not provided, try to resolve via user_id and exchange
        creds = None
        if not (api_key and api_secret):
            if not user_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Missing credentials and user_id for cancel_broker_order",
                )
            creds = get_decrypted_exchange_secret(db=db, user_id=user_id, exchange=exchange)
            if not creds:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Missing credentials for {exchange}",
                )
            api_key = creds["api_key"]
            api_secret = creds["api_secret"]
        adapter = broker_registry.get_broker_adapter(
            exchange,
            api_key=api_key,
            api_secret=api_secret,
        )
        return _cancel_order_via_adapter(
            adapter=adapter,
            symbol=symbol,
            client_order_id=client_order_id,
            market=market,
        )
    finally:
        db.close()
def _cancel_order_via_adapter(*, adapter, symbol: str, client_order_id: str, market: str = "SPOT"):
    """
    Helper to cancel an order via the broker adapter, following the exception handling pattern of send_order/query_order flows.
    """
    db = SessionLocal()
    broker = getattr(adapter, "broker", None) or getattr(adapter, "exchange", None) or getattr(adapter, "name", None) or None
    try:
        log_audit_event(
            db,
            action="order_cancel_requested",
            user_id=None,
            entity_type="execution",
            details={
                "symbol": symbol,
                "client_order_id": client_order_id,
                "market": market,
                "broker": broker,
            },
        )
        db.commit()
        result = adapter.cancel_order(
            symbol=symbol,
            client_order_id=client_order_id,
            market=market,
        )
        log_audit_event(
            db,
            action="order_cancelled",
            user_id=None,
            entity_type="execution",
            details={
                "symbol": symbol,
                "client_order_id": client_order_id,
                "market": market,
                "broker": broker,
                "result": result,
            },
        )
        db.commit()
        return result
    except Exception as exc:
        log_audit_event(
            db,
            action="order_cancel_failed",
            user_id=None,
            entity_type="execution",
            details={
                "symbol": symbol,
                "client_order_id": client_order_id,
                "market": market,
                "broker": broker,
                "error": str(exc),
            },
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Broker cancel_order failed: {exc}",
        )
    finally:
        db.close()
import hashlib
import hmac
import time
import uuid
import requests
import re
from decimal import Decimal

from fastapi import HTTPException, status

from apps.api.app.core.config import settings
from apps.api.app.db.session import SessionLocal
from apps.api.app.services.audit import log_audit_event
from apps.api.app.services.exchange_secrets import get_decrypted_exchange_secret
from apps.worker.app.engine import broker_registry
from apps.worker.app.engine.binance_client import (
    send_test_order,
    get_account_status,
    prepare_binance_market_order_quantity,
    query_order_status,
)
from apps.worker.app.engine.ibkr_client import _build_order_ref, send_ibkr_test_order, get_ibkr_account_status


def _mask_api_key(value: str) -> str:
    if len(value) <= 6:
        return "*" * len(value)
    return f"{value[:3]}***{value[-3:]}"


def _assert_binance_gateway_policy() -> None:
    if not bool(settings.BINANCE_GATEWAY_STRICT_MODE):
        return
    gateway_enabled = bool(settings.BINANCE_GATEWAY_ENABLED and settings.BINANCE_GATEWAY_BASE_URL)
    if not gateway_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Binance strict mode requires gateway enabled",
        )
    if bool(settings.BINANCE_GATEWAY_FALLBACK_DIRECT):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Binance strict mode requires BINANCE_GATEWAY_FALLBACK_DIRECT=false",
        )


def _extract_upstream_code(text: str) -> str | None:
    msg = str(text or "")
    m = re.search(r"\bcode=([A-Za-z0-9_\-]+)", msg)
    if m:
        return m.group(1)
    m = re.search(r'"code"\s*:\s*"?([A-Za-z0-9_\-]+)"?', msg)
    if m:
        return m.group(1)
    return None


def _build_gateway_runtime_error(status_code: int, body_text: str) -> str:
    detail = f"gateway_upstream_error status={int(status_code)}"
    code = _extract_upstream_code(body_text)
    if code:
        detail += f" code={code}"
    return detail


def _post_binance_gateway(endpoint: str, payload: dict) -> requests.Response:
    base = settings.BINANCE_GATEWAY_BASE_URL.rstrip("/")
    url = f"{base}{endpoint}"
    headers = {"Content-Type": "application/json"}
    if settings.BINANCE_GATEWAY_TOKEN:
        headers["X-Internal-Token"] = settings.BINANCE_GATEWAY_TOKEN
    response = requests.post(
        url,
        headers=headers,
        json=payload,
        timeout=max(3, int(settings.BINANCE_GATEWAY_TIMEOUT_SECONDS)),
    )
    if response.status_code >= 400:
        detail = _build_gateway_runtime_error(response.status_code, response.text)
        raise RuntimeError(detail)
    return response


def _sanitize_ibkr_error(exc: Exception) -> str:
    msg = str(exc or "").strip()
    if msg.startswith("ibkr_"):
        return msg
    return "ibkr_runtime_error"


def _is_uncertain_binance_timeout_error(exc: Exception) -> bool:
    if isinstance(exc, requests.Timeout):
        return True
    msg = str(exc or "").lower()
    return "timeout" in msg or "timed out" in msg


def _build_binance_broker_adapter(*, api_key: str, api_secret: str):
    # Monkeypatchable seam for testability; uses broker registry internally.
    import apps.worker.app.engine.binance_adapter as binance_adapter_module
    binance_adapter_module.send_test_order = send_test_order
    binance_adapter_module.query_order_status = query_order_status
    return broker_registry.get_broker_adapter("BINANCE", api_key=api_key, api_secret=api_secret)


def _reconcile_binance_test_order_best_effort(
    *,
    api_key: str,
    api_secret: str,
    symbol: str,
    client_order_id: str,
    market: str,
) -> dict:
    try:
        adapter = _build_binance_broker_adapter(api_key=api_key, api_secret=api_secret)
        return {
            "result": adapter.query_order(
                symbol=symbol,
                client_order_id=client_order_id,
                market=market,
            ),
            "error": None,
        }
    except Exception as exc:
        return {
            "result": None,
            "error": str(exc),
        }


def _classify_binance_reconciliation(*, result: dict | None, error: str | None) -> str:
    msg = str(error or "").lower()
    not_sent_markers = [
        "unknown order",
        "unknown client order",
        "order does not exist",
        "not found",
        "code=-2013",
        "code=-2011",
    ]
    if any(marker in msg for marker in not_sent_markers):
        return "NOT_SENT"

    payload = result if isinstance(result, dict) else None
    if payload is None:
        return "SENT_UNKNOWN"

    code = str(payload.get("code") or "").strip()
    payload_msg = str(payload.get("msg") or payload.get("message") or "").lower()
    if code in {"-2013", "-2011"} or any(marker in payload_msg for marker in not_sent_markers):
        return "NOT_SENT"

    status_value = str(payload.get("status") or payload.get("orderStatus") or "").upper().strip()
    if status_value in {"NEW", "PARTIALLY_FILLED", "FILLED", "PENDING_NEW"}:
        return "EXECUTED"
    if status_value in {"REJECTED", "EXPIRED", "EXPIRED_IN_MATCH", "CANCELED", "CANCELLED"}:
        return "FAILED"
    return "SENT_UNKNOWN"


def prepare_execution_for_user(
    user_id: str,
    exchange: str,
    symbol: str,
    side: str,
    qty: float,
):
    db = SessionLocal()
    try:
        creds = get_decrypted_exchange_secret(
            db=db,
            user_id=user_id,
            exchange=exchange,
        )
        if not creds:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Missing credentials for {exchange}",
            )

        api_key = creds["api_key"]
        api_secret = creds["api_secret"]

        # Build a deterministic dry-run signature payload without exposing raw secrets.
        payload = f"{exchange}|{symbol}|{side}|{qty}"
        signature = hmac.new(
            api_secret.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        log_audit_event(
            db,
            action="execution.prepare",
            user_id=user_id,
            entity_type="execution",
            details={
                "exchange": exchange,
                "symbol": symbol,
                "side": side,
                "qty": qty,
            },
        )
        db.commit()

        return {
            "mode": "dry_run",
            "exchange": exchange,
            "symbol": symbol,
            "side": side,
            "qty": qty,
            "api_key_masked": _mask_api_key(api_key),
            "signature_preview": signature[:12],
        }
    finally:
        db.close()


def resolve_execution_quantity_preview(
    *,
    exchange: str,
    symbol: str,
    side: str,
    requested_qty: float,
) -> dict:
    exchange_up = str(exchange or "").upper().strip()
    symbol_up = str(symbol or "").upper().strip()
    side_up = str(side or "").upper().strip()

    if exchange_up == "BINANCE":
        market = "FUTURES" if side_up == "SELL" else "SPOT"
        qty_meta = prepare_binance_market_order_quantity(
            symbol=symbol_up,
            requested_qty=requested_qty,
            market=market,
        )
        return {
            "exchange": exchange_up,
            "symbol": symbol_up,
            "side": side_up,
            "requested_qty": float(requested_qty),
            "normalized_qty": float(qty_meta.get("normalized_qty") or 0.0),
            "price_estimate": float(qty_meta.get("price") or 0.0),
            "estimated_notional": float(qty_meta.get("estimated_notional") or 0.0),
            "normalization_source": "binance_prepare_market_qty_v1",
            "market": qty_meta.get("market"),
        }

    # IBKR passthrough for sizing/validation alignment
    return {
        "exchange": exchange_up,
        "symbol": symbol_up,
        "side": side_up,
        "requested_qty": float(requested_qty),
        "normalized_qty": float(requested_qty),
        "price_estimate": None,
        "estimated_notional": None,
        "normalization_source": "ibkr_passthrough_v1",
        "market": None,
    }


def execute_binance_test_order_for_user(
    user_id: str,
    symbol: str,
    side: str,
    qty: float,
    intent_key: str | None = None,
    account_id: str | None = None,
):
    db = SessionLocal()
    try:
        _assert_binance_gateway_policy()
        creds = get_decrypted_exchange_secret(
            db=db,
            user_id=user_id,
            exchange="BINANCE",
        )
        if not creds:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing credentials for BINANCE",
            )

        market = "FUTURES" if str(side or "").upper() == "SELL" else "SPOT"
        # Contexto interno del runtime
        runtime_context = {}
        if account_id is not None and str(account_id).strip():
            runtime_context["account_id"] = account_id
        # Intent consumption wiring: persist symbol and market if intent_key present
        if intent_key:
            from apps.worker.app.engine.minimal_execution_runtime import IntentConsumptionStore
            store = IntentConsumptionStore()
            if not store.has_consumed(user_id, "BINANCE", intent_key, account_id):
                store.register_consumption(user_id, "BINANCE", intent_key, account_id, symbol=symbol, market=market)
        try:
            qty_meta = prepare_binance_market_order_quantity(
                symbol=symbol,
                requested_qty=qty,
                market=market,
            )
            client_order_id = _build_binance_client_order_id(
                user_id=user_id,
                symbol=symbol,
                side=side,
                qty=float(qty_meta["normalized_qty"]),
                market=market,
                intent_key=intent_key,
            )
            _send_binance_test_order_with_retry(
                api_key=creds["api_key"],
                api_secret=creds["api_secret"],
                symbol=symbol,
                side=side,
                qty=float(qty_meta["normalized_qty"]),
                client_order_id=client_order_id,
                market=market,
            )
            # Attach broker_execution_id and broker_execution_id_type to the intent consumption record if intent_key is present
            if intent_key:
                from apps.worker.app.engine.minimal_execution_runtime import IntentConsumptionStore
                store = IntentConsumptionStore()
                store.attach_execution(
                    user_id=user_id,
                    broker="BINANCE",
                    intent_key=intent_key,
                    account_id=account_id,
                    execution_id=client_order_id,
                    execution_id_type="client_order_id",
                    symbol=symbol,
                    market=market,
                )
        except Exception as exc:
            details = {
                "symbol": symbol,
                "side": side,
                "qty": qty,
                "client_order_id": locals().get("client_order_id"),
                "normalized_qty": (locals().get("qty_meta") or {}).get("normalized_qty"),
                "market": market,
                "error": str(exc),
            }
            if locals().get("client_order_id") and _is_uncertain_binance_timeout_error(exc):
                reconciliation_attempt = {
                    "client_order_id": client_order_id,
                    **_reconcile_binance_test_order_best_effort(
                        api_key=creds["api_key"],
                        api_secret=creds["api_secret"],
                        symbol=symbol,
                        client_order_id=client_order_id,
                        market=market,
                    ),
                }
                details["reconciliation_attempt"] = reconciliation_attempt
                details["reconciliation_classification"] = _classify_binance_reconciliation(
                    result=reconciliation_attempt.get("result"),
                    error=reconciliation_attempt.get("error"),
                )
            log_audit_event(
                db,
                action="execution.binance.test_order.error",
                user_id=user_id,
                entity_type="execution",
                details=details,
            )
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Binance test order failed: {exc}",
            )

        log_audit_event(
            db,
            action="execution.binance.test_order.success",
            user_id=user_id,
            entity_type="execution",
            details={
                "symbol": symbol,
                "side": side,
                "qty_requested": qty,
                "qty_normalized": qty_meta["normalized_qty"],
                "client_order_id": client_order_id,
                "mode": "testnet_order_test_futures" if market == "FUTURES" else "testnet_order_test",
                "market": market,
            },
        )
        db.commit()

        return {
            "exchange": "BINANCE",
            "mode": "testnet_order_test_futures" if market == "FUTURES" else "testnet_order_test",
            "symbol": symbol.upper(),
            "side": side.upper(),
            "qty": float(qty_meta["normalized_qty"]),
            "qty_requested": float(qty),
            "client_order_id": client_order_id,
            "validation": qty_meta,
            "sent": True,
        }
    finally:
        db.close()


def _build_binance_client_order_id(
    user_id: str,
    symbol: str,
    side: str,
    qty: float,
    market: str,
    intent_key: str | None = None,
) -> str:
    key = str(intent_key or "").strip()
    if key:
        qty_dec = Decimal(str(qty))
        qty_canonical = format(qty_dec, "f")
        if "." in qty_canonical:
            qty_canonical = qty_canonical.rstrip("0").rstrip(".")
        if not qty_canonical:
            qty_canonical = "0"
        canonical = "|".join(
            [
                "autopick_binance_live_v1",
                str(user_id or "").strip().lower(),
                str(symbol or "").strip().upper(),
                str(side or "").strip().upper(),
                qty_canonical,
                str(market or "").strip().upper(),
                key,
            ]
        )
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return f"csi{digest[:33]}"

    # Legacy behavior outside hardened live auto-pick flow.
    seed = f"{user_id}|{symbol.upper()}|{side.upper()}|{qty}|{uuid.uuid4().hex[:10]}"
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:24]
    return f"cs{digest}"


def _is_retryable_binance_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    retry_markers = [
        "429",
        "status=429",
        "status 429",
        "502",
        "503",
        "504",
        "timeout",
        "temporarily unavailable",
        "connection reset",
    ]
    return any(m in msg for m in retry_markers)


def _send_binance_test_order_with_retry(
    *,
    api_key: str,
    api_secret: str,
    symbol: str,
    side: str,
    qty: float,
    client_order_id: str,
    market: str = "SPOT",
) -> None:
    attempts = max(1, int(settings.BINANCE_ORDER_RETRY_MAX_ATTEMPTS or 2))
    backoff_base = max(0.05, float(settings.BINANCE_ORDER_RETRY_BACKOFF_SECONDS or 0.7))
    last_exc = None
    for i in range(attempts):
        try:
            _send_binance_test_order(
                api_key=api_key,
                api_secret=api_secret,
                symbol=symbol,
                side=side,
                qty=qty,
                client_order_id=client_order_id,
                market=market,
            )
            return
        except Exception as exc:
            last_exc = exc
            is_last = i >= attempts - 1
            if is_last or not _is_retryable_binance_error(exc):
                break
            time.sleep(backoff_base * (2 ** i))
    if last_exc:
        raise last_exc


def _send_binance_test_order(
    api_key: str,
    api_secret: str,
    symbol: str,
    side: str,
    qty: float,
    client_order_id: str | None = None,
    market: str = "SPOT",
) -> None:
    if not client_order_id:
        raise RuntimeError("kernel_dispatch_guard: missing client_order_id")

    adapter = _build_binance_broker_adapter(api_key=api_key, api_secret=api_secret)

    gateway_enabled = bool(settings.BINANCE_GATEWAY_ENABLED and settings.BINANCE_GATEWAY_BASE_URL)
    if not gateway_enabled:
        _retry_once_on_gateway_502(
            adapter.send_order,
            symbol=symbol,
            side=side,
            quantity=qty,
            client_order_id=client_order_id,
            market=market,
        )
        return

    try:
        _send_binance_test_order_via_gateway(
            api_key=api_key,
            api_secret=api_secret,
            symbol=symbol,
            side=side,
            qty=qty,
            client_order_id=client_order_id,
            market=market,
        )
    except Exception as exc:
        if not settings.BINANCE_GATEWAY_FALLBACK_DIRECT:
            raise
        if "gateway_upstream_error status=" in str(exc or ""):
            raise
        _retry_once_on_gateway_502(
            adapter.send_order,
            symbol=symbol,
            side=side,
            quantity=qty,
            client_order_id=client_order_id,
            market=market,
        )

# Refactored helper for single retry on gateway 502
def _retry_once_on_gateway_502(send_func, *args, **kwargs):
    """
    Calls send_func, retries once only if error contains 'gateway_upstream_error status=502'.
    No retry for timeout/timed out. No retry for reconciliation/query.
    """
    try:
        return send_func(*args, **kwargs)
    except Exception as exc:
        msg = str(exc or "")
        if "gateway_upstream_error status=502" in msg and not ("timeout" in msg or "timed out" in msg):
            try:
                return send_func(*args, **kwargs)
            except Exception as exc2:
                raise exc2
        raise exc



def _send_binance_test_order_via_gateway(
    api_key: str,
    api_secret: str,
    symbol: str,
    side: str,
    qty: float,
    client_order_id: str | None = None,
    market: str = "SPOT",
) -> None:
    payload = {
        "api_key": api_key,
        "api_secret": api_secret,
        "symbol": symbol.upper(),
        "side": side.upper(),
        "qty": qty,
        "client_order_id": client_order_id,
        "market": str(market or "SPOT").upper(),
    }
    _post_binance_gateway("/binance/test-order", payload)


def _get_binance_account_status(
    api_key: str,
    api_secret: str,
):
    gateway_enabled = bool(settings.BINANCE_GATEWAY_ENABLED and settings.BINANCE_GATEWAY_BASE_URL)
    if not gateway_enabled:
        return get_account_status(api_key=api_key, api_secret=api_secret)
    try:
        return _get_binance_account_status_via_gateway(
            api_key=api_key,
            api_secret=api_secret,
        )
    except Exception:
        if not settings.BINANCE_GATEWAY_FALLBACK_DIRECT:
            raise
        return get_account_status(api_key=api_key, api_secret=api_secret)


def _get_binance_account_status_via_gateway(
    api_key: str,
    api_secret: str,
):
    payload = {"api_key": api_key, "api_secret": api_secret}
    response = _post_binance_gateway("/binance/account-status", payload)
    return response.json()


def execute_ibkr_test_order_for_user(
    user_id: str,
    symbol: str,
    side: str,
    qty: float,
    account_id: str | None = None,
):
    db = SessionLocal()
    from apps.worker.app.engine.minimal_execution_runtime import IntentConsumptionStore, build_intent_consumption_key
    try:
        creds = get_decrypted_exchange_secret(
            db=db,
            user_id=user_id,
            exchange="IBKR",
        )
        if not creds:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing credentials for IBKR",
            )

        # Enforcement de consumo de intent_key por contexto
        import inspect
        intent_key = None
        try:
            frame = inspect.currentframe()
            if frame and frame.f_back and "intent_key" in frame.f_back.f_locals:
                intent_key = frame.f_back.f_locals["intent_key"]
        except Exception:
            pass
        if intent_key:
            store = IntentConsumptionStore()
            # Audit: intent consumption blocked
            if store.has_consumed(user_id, "IBKR", intent_key, account_id):
                log_audit_event(
                    db,
                    action="execution.ibkr.intent_consumption.blocked",
                    user_id=user_id,
                    entity_type="execution",
                    details={
                        "intent_key": intent_key,
                        "user_id": user_id,
                        "broker": "IBKR",
                        "account_id": account_id,
                        "status": "blocked"
                    },
                )
                db.commit()
                return {
                    "exchange": "IBKR",
                    "mode": "blocked_duplicate_intent_key",
                    "symbol": symbol.upper(),
                    "side": side.upper(),
                    "qty": qty,
                    "sent": False,
                    "order_ref": None,
                    "reason": "intent_key already consumed for this context"
                }
            # Audit: intent consumption accepted
            store.register_consumption(user_id, "IBKR", intent_key, account_id)
            log_audit_event(
                db,
                action="execution.ibkr.intent_consumption.accepted",
                user_id=user_id,
                entity_type="execution",
                details={
                    "intent_key": intent_key,
                    "user_id": user_id,
                    "broker": "IBKR",
                    "account_id": account_id,
                    "status": "accepted"
                },
            )
            db.commit()

        order_ref = _build_order_ref(
            api_key=creds["api_key"],
            symbol=symbol,
            side=side,
            quantity=qty,
        )

        # Contexto interno del runtime
        runtime_context = {}
        if account_id is not None and str(account_id).strip():
            runtime_context["account_id"] = account_id

        try:
            result = send_ibkr_test_order(
                api_key=creds["api_key"],
                api_secret=creds["api_secret"],
                symbol=symbol,
                side=side,
                quantity=qty,
                order_ref=order_ref,
            )
        except Exception as exc:
            err_detail = _sanitize_ibkr_error(exc)
            log_audit_event(
                db,
                action="execution.ibkr.test_order.error",
                user_id=user_id,
                entity_type="execution",
                details={
                    "symbol": symbol,
                    "side": side,
                    "qty": qty,
                    "error": err_detail,
                },
            )
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=err_detail,
            )

        mode = "paper_bridge_test" if result.get("mode") == "bridge" else "paper_simulated_test"
        order_ref = result.get("order_ref", "")
        log_audit_event(
            db,
            action="execution.ibkr.test_order.success",
            user_id=user_id,
            entity_type="execution",
            details={"symbol": symbol, "side": side, "qty": qty, "mode": mode, "order_ref": order_ref},
        )
        db.commit()

        return {
            "exchange": "IBKR",
            "mode": mode,
            "symbol": symbol.upper(),
            "side": side.upper(),
            "qty": qty,
            "sent": True,
            "order_ref": order_ref,
        }
    finally:
        db.close()


def get_binance_account_status_for_user(user_id: str):
    db = SessionLocal()
    try:
        _assert_binance_gateway_policy()
        creds = get_decrypted_exchange_secret(
            db=db,
            user_id=user_id,
            exchange="BINANCE",
        )
        if not creds:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing credentials for BINANCE",
            )
        try:
            raw = _get_binance_account_status(
                api_key=creds["api_key"],
                api_secret=creds["api_secret"],
            )
        except Exception as exc:
            log_audit_event(
                db,
                action="execution.binance.account_status.error",
                user_id=user_id,
                entity_type="execution",
                details={"error": str(exc)},
            )
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Binance account status failed: {exc}",
            )

        balances = []
        for b in (raw.get("balances") or []):
            free = float(b.get("free", 0) or 0)
            locked = float(b.get("locked", 0) or 0)
            total = free + locked
            if total <= 0:
                continue
            balances.append(
                {
                    "asset": str(b.get("asset", "")),
                    "free": free,
                    "locked": locked,
                    "total": total,
                }
            )
        balances.sort(key=lambda x: x["total"], reverse=True)
        balances = balances[:20]
        out = {
            "exchange": "BINANCE",
            "mode": "testnet_account",
            "account_id": None,
            "can_trade": bool(raw.get("canTrade", True)),
            "balances": balances,
            "open_orders": None,
            "positions": [],
            "metrics": {
                "maker_commission": raw.get("makerCommission"),
                "taker_commission": raw.get("takerCommission"),
                "permissions": raw.get("permissions", []),
                "update_time": raw.get("updateTime"),
            },
        }
        log_audit_event(
            db,
            action="execution.binance.account_status.success",
            user_id=user_id,
            entity_type="execution",
            details={"balances_count": len(balances), "can_trade": out["can_trade"]},
        )
        db.commit()
        return out
    finally:
        db.close()


def get_binance_spot_usdt_free_for_user(user_id: str) -> dict:
    db = SessionLocal()
    try:
        _assert_binance_gateway_policy()
        creds = get_decrypted_exchange_secret(
            db=db,
            user_id=user_id,
            exchange="BINANCE",
        )
        if not creds:
            raise RuntimeError("broker_status_unavailable")

        try:
            raw = _get_binance_account_status(
                api_key=creds["api_key"],
                api_secret=creds["api_secret"],
            )
        except Exception as exc:
            log_audit_event(
                db,
                action="execution.binance.spot_usdt_guard.error",
                user_id=user_id,
                entity_type="execution",
                details={"error": str(exc)},
            )
            db.commit()
            raise RuntimeError("broker_status_unavailable")

        if not isinstance(raw, dict):
            raise RuntimeError("broker_status_unavailable")

        can_trade = bool(raw.get("canTrade", True))
        usdt_free = None
        for balance in (raw.get("balances") or []):
            asset = str((balance or {}).get("asset") or "").strip().upper()
            if asset != "USDT":
                continue
            try:
                usdt_free = float((balance or {}).get("free", 0) or 0)
            except Exception:
                usdt_free = None
            break

        log_audit_event(
            db,
            action="execution.binance.spot_usdt_guard.success",
            user_id=user_id,
            entity_type="execution",
            details={
                "can_trade": can_trade,
                "usdt_free_available": usdt_free is not None,
            },
        )
        db.commit()
        return {
            "can_trade": can_trade,
            "usdt_free": usdt_free,
        }
    finally:
        db.close()


def get_ibkr_account_status_for_user(user_id: str):
    db = SessionLocal()
    try:
        creds = get_decrypted_exchange_secret(
            db=db,
            user_id=user_id,
            exchange="IBKR",
        )
        if not creds:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing credentials for IBKR",
            )
        try:
            raw = get_ibkr_account_status(
                api_key=creds["api_key"],
                api_secret=creds["api_secret"],
            )
        except Exception as exc:
            err_detail = _sanitize_ibkr_error(exc)
            log_audit_event(
                db,
                action="execution.ibkr.account_status.error",
                user_id=user_id,
                entity_type="execution",
                details={"error": err_detail},
            )
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=err_detail,
            )

        positions = []
        for p in (raw.get("positions") or []):
            positions.append(
                {
                    "symbol": str(p.get("symbol", "")),
                    "qty": p.get("qty"),
                    "avg_price": p.get("avg_price"),
                    "market_value": p.get("market_value"),
                    "unrealized_pnl": p.get("unrealized_pnl"),
                }
            )
        out = {
            "exchange": "IBKR",
            "mode": raw.get("mode", "simulated"),
            "account_id": raw.get("account_id"),
            "can_trade": bool(raw.get("can_trade", True)),
            "balances": [],
            "open_orders": len(raw.get("open_orders") or []),
            "positions": positions,
            "metrics": {
                "currency": raw.get("currency"),
                "cash": raw.get("cash"),
                "buying_power": raw.get("buying_power"),
                "net_liquidation": raw.get("net_liquidation"),
            },
        }
        log_audit_event(
            db,
            action="execution.ibkr.account_status.success",
            user_id=user_id,
            entity_type="execution",
            details={
                "mode": out["mode"],
                "positions_count": len(positions),
                "can_trade": out["can_trade"],
            },
        )
        db.commit()
        return out
    finally:
        db.close()
