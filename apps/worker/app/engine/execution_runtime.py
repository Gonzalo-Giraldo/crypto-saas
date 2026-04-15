import hashlib
import hmac
import time
import requests
import re
from decimal import Decimal
            
from fastapi import HTTPException, status
from sqlalchemy import text
                
from apps.api.app.core.config import settings
from apps.api.app.db.session import SessionLocal
from apps.api.app.services.audit import log_audit_event
from apps.api.app.services.exchange_secrets import get_decrypted_exchange_secret
from apps.worker.app.engine.minimal_execution_runtime import IntentConsumptionStore
from apps.worker.app.engine import broker_registry
from apps.worker.app.engine.binance_client import (
    send_test_order,
    get_account_status,
    prepare_binance_market_order_quantity,
    query_order_status,
)
from apps.worker.app.engine.ibkr_client import _build_order_ref, send_ibkr_test_order, get_ibkr_account_status


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
    base = str(settings.BINANCE_GATEWAY_BASE_URL or "").rstrip("/")
    if not base:
        raise RuntimeError("gateway_upstream_error status=502: missing_gateway_base_url")

    url = f"{base}{endpoint}"
    headers = {"Content-Type": "application/json"}
    token = str(settings.BINANCE_GATEWAY_TOKEN or "").strip()
    if token:
        headers["X-Internal-Token"] = token

    try:
        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=max(3, int(settings.BINANCE_GATEWAY_TIMEOUT_SECONDS)),
        )
    except Exception as exc:
        raise RuntimeError(f"gateway_upstream_error status=502: {exc}")

    if response.status_code >= 400:
        raise RuntimeError(f"gateway_upstream_error status={response.status_code}: {response.text}")

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
            def _build_consumer(user_id, broker, account_id=None):
                acc = account_id if (account_id is not None and str(account_id).strip()) else "no-account"
                return f"{user_id}:{broker}:{acc}"

            intent_id = str(intent_key)
            consumer = _build_consumer(user_id, "BINANCE", account_id)

            if hasattr(db, "execute"):
                # Check if already consumed
                result = db.execute(
                    text("SELECT 1 FROM intent_consumptions WHERE intent_id = :intent_id AND consumer = :consumer LIMIT 1"),
                    {"intent_id": intent_id, "consumer": consumer}
                ).fetchone()
                if result is None:
                    db.execute(
                        text("INSERT INTO intent_consumptions (intent_id, consumer) VALUES (:intent_id, :consumer) ON CONFLICT (intent_id, consumer) DO NOTHING"),
                        {"intent_id": intent_id, "consumer": consumer}
                    )
                    db.commit()
            else:
                # Entorno sin soporte de SQL execution explícita (por ejemplo, FakeDB de tests).
                # Continuar sin consumo persistente de intent_key en este contexto.
                pass
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
    if not key:
        raise RuntimeError("kernel_dispatch_guard: missing intent_key for deterministic client_order_id")
    seed = f"{user_id}|{symbol.upper()}|{side.upper()}|{qty}|{key}"
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

    if gateway_enabled:
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
            return
        except Exception as exc:
            msg = str(exc or "")

            # retry SOLO si es 502
            if "gateway_upstream_error status=502" in msg:
                return adapter.send_order(
                    symbol=symbol,
                    side=side,
                    quantity=qty,
                    client_order_id=client_order_id,
                    market=market,
                )

            if not settings.BINANCE_GATEWAY_FALLBACK_DIRECT:
                raise

            # fallback controlado
            return adapter.send_order(
                symbol=symbol,
                side=side,
                quantity=qty,
                client_order_id=client_order_id,
                market=market,
            )

    # sin gateway
    return adapter.send_order(
        symbol=symbol,
        side=side,
        quantity=qty,
        client_order_id=client_order_id,
        market=market,
    )


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
    intent_key: str | None = None,
):
    db = SessionLocal()
    # Implementación directa de consumo de intents en DB
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

        # Observabilidad: log intent_key recibido
        print({
            "event": "ibkr_test_order_intent_key_entry",
            "intent_key": intent_key,
            "user_id": user_id,
            "symbol": symbol,
            "side": side,
            "qty": qty,
            "account_id": account_id,
        })

        # Enforcement de consumo de intent_key por contexto (explícito)
        if intent_key:
            def _build_consumer(user_id, broker, account_id=None):
                acc = account_id if (account_id is not None and str(account_id).strip()) else "no-account"
                return f"{user_id}:{broker}:{acc}"

            intent_id = str(intent_key)
            consumer = _build_consumer(user_id, "IBKR", account_id)
            print({
                "event": "ibkr_test_order_intent_consumption_check",
                "intent_id": intent_id,
                "consumer": consumer,
            })
            # Check if already consumed
            result = db.execute(
                text("SELECT 1 FROM intent_consumptions WHERE intent_id = :intent_id AND consumer = :consumer LIMIT 1"),
                {"intent_id": intent_id, "consumer": consumer}
            ).fetchone()
            print({
                "event": "ibkr_test_order_intent_consumption_select_result",
                "found": result is not None,
            })
            if result is not None:
                print({
                    "event": "ibkr_test_order_intent_consumption_blocked_return",
                    "sent": False,
                })
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
                order_ref = ""
                return {
                    "exchange": "IBKR",
                    "mode": "blocked_duplicate_intent_key",
                    "symbol": symbol.upper(),
                    "side": side.upper(),
                    "qty": qty,
                    "sent": False,
                    "order_ref": str(order_ref),
                    "reason": "intent_key already consumed for this context"
                }
            # Registrar consumo
            print({
                "event": "ibkr_test_order_intent_consumption_insert",
                "intent_id": intent_id,
                "consumer": consumer,
            })
            db.execute(
                text("INSERT INTO intent_consumptions (intent_id, consumer) VALUES (:intent_id, :consumer) ON CONFLICT (intent_id, consumer) DO NOTHING"),
                {"intent_id": intent_id, "consumer": consumer}
            )
            db.commit()
            print({
                "event": "ibkr_test_order_intent_consumption_commit",
                "intent_id": intent_id,
                "consumer": consumer,
            })
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


        # --- IBKR SELL GUARD: Prevent over-selling ---
        if str(side).upper() == "SELL":
            # 1. Get reconciled position for user/account/symbol
            reconciled_position_qty = 0.0
            try:
                acct_status = get_ibkr_account_status_for_user(user_id)
                # Find position for this symbol (case-insensitive match)
                for pos in acct_status.get("positions", []):
                    if str(pos.get("symbol", "")).upper() == str(symbol).upper():
                        reconciled_position_qty = float(pos.get("qty") or 0.0)
                        break
            except Exception as exc:
                log_audit_event(
                    db,
                    action="execution.ibkr.sell_guard.error",
                    user_id=user_id,
                    entity_type="execution",
                    details={
                        "symbol": symbol,
                        "side": side,
                        "qty": qty,
                        "error": f"account_status_error: {exc}",
                    },
                )
                db.commit()
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"IBKR sell guard failed to fetch account status: {exc}",
                )

            # 2. Query open SELL dossiers for this user/account/symbol
            # Only consider dossiers with side=SELL and open/partial/unknown lifecycle status
            reserved_sell_qty_open = 0.0
            open_statuses = (
                "open",
                "partial_active",
                "partial_stale",
                "unknown_broker_state",
            )
            # Query intent_consumptions for open SELLs
            rows = db.execute(
                text("""
                    SELECT expected_qty, filled_qty, remaining_qty, lifecycle_status
                    FROM intent_consumptions
                    WHERE user_id = :user_id
                      AND broker = 'IBKR'
                      AND symbol = :symbol
                      AND side = 'SELL'
                      AND account_id IS NOT DISTINCT FROM :account_id
                      AND lifecycle_status IN :open_statuses
                """),
                {
                    "user_id": user_id,
                    "symbol": str(symbol).upper(),
                    "account_id": account_id if account_id is not None else None,
                    "open_statuses": tuple(open_statuses),
                },
            ).fetchall()
            for row in rows:
                # Use remaining_qty if present, else fallback to expected_qty - filled_qty, else expected_qty
                rq = row[2] if row[2] is not None else (
                    (row[0] or 0.0) - (row[1] or 0.0) if row[0] is not None and row[1] is not None else (row[0] or 0.0)
                )
                reserved_sell_qty_open += float(rq or 0.0)

            available_sell_qty = max(reconciled_position_qty - reserved_sell_qty_open, 0.0)
            if float(qty) > available_sell_qty:
                log_audit_event(
                    db,
                    action="execution.ibkr.sell_guard.blocked",
                    user_id=user_id,
                    entity_type="execution",
                    details={
                        "symbol": symbol,
                        "side": side,
                        "qty": qty,
                        "reconciled_position_qty": reconciled_position_qty,
                        "reserved_sell_qty_open": reserved_sell_qty_open,
                        "available_sell_qty": available_sell_qty,
                        "reason": "SELL qty exceeds available position after reserving open SELLs",
                    },
                )
                db.commit()
                return {
                    "exchange": "IBKR",
                    "mode": "blocked_sell_guard",
                    "symbol": symbol.upper(),
                    "side": side.upper(),
                    "qty": qty,
                    "sent": False,
                    "reason": "SELL qty exceeds available position after reserving open SELLs",
                    "reconciled_position_qty": reconciled_position_qty,
                    "reserved_sell_qty_open": reserved_sell_qty_open,
                    "available_sell_qty": available_sell_qty,
                }

        order_ref = _build_order_ref(
            api_key=creds["api_key"],
            intent_key=intent_key,
            user_id=user_id,
            broker="IBKR",
            account_id=account_id,
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
        order_ref = str(result.get("order_ref") or "")
        log_audit_event(
            db,
            action="execution.ibkr.test_order.success",
            user_id=user_id,
            entity_type="execution",
            details={"symbol": symbol, "side": side, "qty": qty, "mode": mode, "order_ref": order_ref},
        )
        db.commit()


        # Fix mínimo: actualizar correlación intent -> execution en intent_consumptions
        if intent_key:
            consumer = _build_consumer(user_id, "IBKR", account_id)
            result = db.execute(
                text("""
                    UPDATE intent_consumptions
                    SET execution_ref = :order_ref, symbol = :symbol
                    WHERE intent_id = :intent_id AND consumer = :consumer
                """),
                {
                    "order_ref": order_ref,
                    "symbol": symbol,
                    "intent_id": str(intent_key),
                    "consumer": consumer,
                }
            )
            db.commit()
            if result.rowcount != 1:
                print({"event": "ibkr_update_intent_consumptions_rowcount_mismatch", "rowcount": result.rowcount, "intent_id": intent_key, "consumer": consumer})

        print({
            "event": "ibkr_test_order_return_sent_true",
            "sent": True,
            "order_ref": order_ref,
        })
        # --- Integración de reconciliación IBKR ---
        from apps.api.app.services.ibkr_reconciliation import get_ibkr_reconciliation_source, reconcile_ibkr_fills, persist_ibkr_fills
        fills = get_ibkr_reconciliation_source(
            execution_ref=order_ref,
            user_id=user_id,
            account_id=account_id,
            db=db,
            mode="ibkr_real",
        )

        persist_ibkr_fills(db, fills)

        reconciliation = reconcile_ibkr_fills(fills, expected_qty=qty)
        reconciliation_status = reconciliation["status"] 
        total_qty = reconciliation.get("total_qty", 0)
        expected_qty = qty
        remaining_qty = None
        if expected_qty is not None:
            remaining_qty = max(0, expected_qty - total_qty)
        execution_complete = reconciliation_status == "filled"
        requires_manual_review = reconciliation_status == "partial"        

        # Add broker_trade_time: earliest fill timestamp, or None if no fills
        broker_trade_time = None
        if fills and hasattr(fills[0], "timestamp"):
            # Use the earliest fill's timestamp (trade.time from IBKR)
            broker_trade_time = fills[0].timestamp

        return {
            "exchange": "IBKR",
            "mode": mode,
            "symbol": symbol.upper(),
            "side": side.upper(),
            "qty": qty,
            "sent": True,
            "order_ref": order_ref,
            "reconciliation_status": reconciliation_status,            
            "execution_complete": execution_complete,
            "expected_qty": expected_qty,
            "filled_qty": total_qty,
            "remaining_qty": remaining_qty,
            "requires_manual_review": requires_manual_review,
            "broker_trade_time": broker_trade_time,  # Sourced from first fill's trade.time (fill event, not order ack)
            "reconciliation": reconciliation,
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
            # VALIDACIÓN CRÍTICA: no permitir estado incompleto
            if raw.get("mode") == "bridge":
                if "positions" not in raw:
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail="ibkr_runtime_incomplete: positions not available",
                    )
        except HTTPException:
            raise
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
