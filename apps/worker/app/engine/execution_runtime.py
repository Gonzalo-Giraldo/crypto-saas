import hashlib
import hmac
import time
import uuid
import requests

from fastapi import HTTPException, status

from apps.api.app.core.config import settings
from apps.api.app.db.session import SessionLocal
from apps.api.app.services.audit import log_audit_event
from apps.api.app.services.exchange_secrets import get_decrypted_exchange_secret
from apps.worker.app.engine.binance_client import (
    send_test_order,
    get_account_status,
    prepare_binance_market_order_quantity,
)
from apps.worker.app.engine.ibkr_client import send_ibkr_test_order, get_ibkr_account_status


def _mask_api_key(value: str) -> str:
    if len(value) <= 6:
        return "*" * len(value)
    return f"{value[:3]}***{value[-3:]}"


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


def execute_binance_test_order_for_user(
    user_id: str,
    symbol: str,
    side: str,
    qty: float,
):
    db = SessionLocal()
    try:
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
            qty_meta = prepare_binance_market_order_quantity(
                symbol=symbol,
                requested_qty=qty,
            )
            client_order_id = _build_binance_client_order_id(
                user_id=user_id,
                symbol=symbol,
                side=side,
                qty=float(qty_meta["normalized_qty"]),
            )
            _send_binance_test_order_with_retry(
                api_key=creds["api_key"],
                api_secret=creds["api_secret"],
                symbol=symbol,
                side=side,
                qty=float(qty_meta["normalized_qty"]),
                client_order_id=client_order_id,
            )
        except Exception as exc:
            log_audit_event(
                db,
                action="execution.binance.test_order.error",
                user_id=user_id,
                entity_type="execution",
                details={
                    "symbol": symbol,
                    "side": side,
                    "qty": qty,
                    "client_order_id": locals().get("client_order_id"),
                    "normalized_qty": (locals().get("qty_meta") or {}).get("normalized_qty"),
                    "error": str(exc),
                },
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
                "mode": "testnet_order_test",
            },
        )
        db.commit()

        return {
            "exchange": "BINANCE",
            "mode": "testnet_order_test",
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
) -> str:
    # Prefix + stable components keeps retries idempotent for the same function call.
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
) -> None:
    gateway_enabled = bool(settings.BINANCE_GATEWAY_ENABLED and settings.BINANCE_GATEWAY_BASE_URL)
    if not gateway_enabled:
        send_test_order(
            api_key=api_key,
            api_secret=api_secret,
            symbol=symbol,
            side=side,
            quantity=qty,
            client_order_id=client_order_id,
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
        )
    except Exception:
        if not settings.BINANCE_GATEWAY_FALLBACK_DIRECT:
            raise
        send_test_order(
            api_key=api_key,
            api_secret=api_secret,
            symbol=symbol,
            side=side,
            quantity=qty,
            client_order_id=client_order_id,
        )


def _send_binance_test_order_via_gateway(
    api_key: str,
    api_secret: str,
    symbol: str,
    side: str,
    qty: float,
    client_order_id: str | None = None,
) -> None:
    base = settings.BINANCE_GATEWAY_BASE_URL.rstrip("/")
    url = f"{base}/binance/test-order"
    headers = {"Content-Type": "application/json"}
    if settings.BINANCE_GATEWAY_TOKEN:
        headers["X-Internal-Token"] = settings.BINANCE_GATEWAY_TOKEN

    payload = {
        "api_key": api_key,
        "api_secret": api_secret,
        "symbol": symbol.upper(),
        "side": side.upper(),
        "qty": qty,
        "client_order_id": client_order_id,
    }

    response = requests.post(
        url,
        headers=headers,
        json=payload,
        timeout=max(3, int(settings.BINANCE_GATEWAY_TIMEOUT_SECONDS)),
    )
    if response.status_code >= 400:
        detail = response.text
        raise RuntimeError(f"Binance gateway error {response.status_code}: {detail}")


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
    base = settings.BINANCE_GATEWAY_BASE_URL.rstrip("/")
    url = f"{base}/binance/account-status"
    headers = {"Content-Type": "application/json"}
    if settings.BINANCE_GATEWAY_TOKEN:
        headers["X-Internal-Token"] = settings.BINANCE_GATEWAY_TOKEN
    payload = {"api_key": api_key, "api_secret": api_secret}
    response = requests.post(
        url,
        headers=headers,
        json=payload,
        timeout=max(3, int(settings.BINANCE_GATEWAY_TIMEOUT_SECONDS)),
    )
    if response.status_code >= 400:
        detail = response.text
        raise RuntimeError(f"Binance gateway error {response.status_code}: {detail}")
    return response.json()


def execute_ibkr_test_order_for_user(
    user_id: str,
    symbol: str,
    side: str,
    qty: float,
):
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
            result = send_ibkr_test_order(
                api_key=creds["api_key"],
                api_secret=creds["api_secret"],
                symbol=symbol,
                side=side,
                quantity=qty,
            )
        except Exception as exc:
            log_audit_event(
                db,
                action="execution.ibkr.test_order.error",
                user_id=user_id,
                entity_type="execution",
                details={
                    "symbol": symbol,
                    "side": side,
                    "qty": qty,
                    "error": str(exc),
                },
            )
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"IBKR test order failed: {exc}",
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
            log_audit_event(
                db,
                action="execution.ibkr.account_status.error",
                user_id=user_id,
                entity_type="execution",
                details={"error": str(exc)},
            )
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"IBKR account status failed: {exc}",
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
