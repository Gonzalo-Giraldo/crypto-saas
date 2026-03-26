
"""
IBKR Client Transport Module
---------------------------
This module provides the explicit client seam for Interactive Brokers (IBKR) lifecycle operations.
Unlike Binance, there is no gateway abstraction for IBKR in this project. All transport and protocol
handling for IBKR order operations will be implemented directly in this module.

This groundwork provides placeholder functions for the main IBKR order lifecycle actions. These are
not yet implemented or wired to any adapter or runtime logic.
"""

def get_ibkr_trades(api_key: str, api_secret: str, symbol: str, client_order_id: str) -> dict:
    """
    Read-only seam to fetch IBKR trades/fills for a given order.
    If IBKR_BRIDGE_BASE_URL is set, queries the bridge; otherwise returns a seam stub.
    """
    from apps.api.app.core.config import settings
    import json
    import hashlib
    import hmac

    symbol_norm = str(symbol or "").upper().strip()
    client_order_id_norm = str(client_order_id or "").strip()
    if not symbol_norm:
        raise RuntimeError("ibkr_trades_input_error: missing symbol")
    if not client_order_id_norm:
        raise RuntimeError("ibkr_trades_input_error: missing client_order_id")

    if getattr(settings, "IBKR_BRIDGE_BASE_URL", None):
        payload = {
            "symbol": symbol_norm,
            "client_order_id": client_order_id_norm,
        }
        payload_raw = json.dumps(payload, separators=(",", ":"))
        signature = hmac.new(
            api_secret.encode("utf-8"),
            payload_raw.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        headers = {
            "X-API-KEY": api_key,
            "X-SIGNATURE": signature,
            "Content-Type": "application/json",
        }
        url = f"{settings.IBKR_BRIDGE_BASE_URL.rstrip('/')}/ibkr/paper/trades"
        response = _post_bridge(url, payload_raw=payload_raw, headers=headers, timeout=12)
        if response.status_code >= 400:
            raise RuntimeError(f"ibkr_bridge_trades_error {response.status_code}: {response.text}")
        out = response.json()
        out["mode"] = "bridge"
        return out
    # Seam stub if no bridge
    return {"mode": "ibkr_trades_seam", "trades": []}
"""
IBKR Client Transport Module
---------------------------
This module provides the explicit client seam for Interactive Brokers (IBKR) lifecycle operations.
Unlike Binance, there is no gateway abstraction for IBKR in this project. All transport and protocol
handling for IBKR order operations will be implemented directly in this module.

This groundwork provides placeholder functions for the main IBKR order lifecycle actions. These are
not yet implemented or wired to any adapter or runtime logic.
"""

from typing import Any
import requests
from apps.api.app.core.config import settings
import json
import hashlib
import hmac

def send_order(*, api_key: str, api_secret: str, symbol: str, side: str, quantity: float, order_ref: str, **kwargs):
    """
    Send an order to IBKR. This is the current transport seam for IBKR send_order.
    This implementation is broker-neutral and does not assume any gateway or futures logic.
    """
    # If a real IBKR execution seam exists, delegate to it here (none found in repo).
    # Thin placeholder: return a minimal result and mark as transport seam.
    return {
        "status": "sent",
        "symbol": symbol,
        "side": side,
        "quantity": quantity,
        "order_ref": order_ref,
        "mode": "ibkr_send_order_seam",
    }

def query_order_status(*, api_key: str, api_secret: str, symbol: str, client_order_id: str, **kwargs):
    """
    Query the status of an order from IBKR. This is the current transport seam for IBKR query_order_status.
    This implementation is broker-neutral and does not assume any gateway or futures logic.
    """
    # If a real IBKR query seam exists, delegate to it here (none found in repo).
    # Thin placeholder: return a minimal result and mark as transport seam.
    return {
        "status": "queried",
        "symbol": symbol,
        "client_order_id": client_order_id,
        "mode": "ibkr_query_order_status_seam",
    }

def cancel_order(*, api_key: str, api_secret: str, symbol: str, client_order_id: str, **kwargs):
    """
    Cancel an order on IBKR. This is the current transport seam for IBKR cancel_order.
    This implementation is broker-neutral and does not assume any gateway or futures logic.
    """
    # If a real IBKR cancel seam exists, delegate to it here (none found in repo).
    # Thin placeholder: return a minimal result and mark as transport seam.
    return {
        "status": "cancelled",
        "symbol": symbol,
        "client_order_id": client_order_id,
        "mode": "ibkr_cancel_order_seam",
    }


def _post_bridge(url: str, *, payload_raw: str, headers: dict, timeout: int = 12) -> requests.Response:
    try:
        return requests.post(url, data=payload_raw, headers=headers, timeout=timeout)
    except requests.RequestException:
        raise RuntimeError("ibkr_upstream_unreachable")


from apps.worker.app.engine.minimal_execution_runtime import normalize_order_ref

def generate_order_ref(
    *,
    order_ref: str | None = None,
    intent_key: str | None = None,
    user_id: str | None = None,
    broker: str | None = None,
    account_id: str | None = None,
    strategy_id: str | None = None,
    symbol: str | None = None,
    side: str | None = None,
    **kwargs,
) -> str:
    """
    Contrato oficial de generación de order_ref:
    - Si recibe order_ref explícita no vacía, la normaliza y la devuelve.
    - Si recibe intent_key no vacío, genera determinísticamente order_ref usando intent_key, user_id, broker, account_id ("no-account" si falta).
    - Si no, fallback determinístico igual a la lógica anterior.
    - Siempre pasa por normalize_order_ref antes de devolver.
    """
    norm_order_ref = normalize_order_ref(order_ref) if order_ref is not None else None
    if norm_order_ref:
        return norm_order_ref
    norm_intent_key = normalize_order_ref(intent_key) if intent_key is not None else None
    if norm_intent_key:
        acc = account_id if (account_id is not None and str(account_id).strip()) else "no-account"
        ref = f"{norm_intent_key}::{user_id or ''}::{broker or ''}::{acc}"
        return normalize_order_ref(ref)
    # Fallback determinístico igual a la lógica anterior
    parts = [p for p in (user_id, strategy_id, symbol, side) if p]
    if parts:
        return normalize_order_ref("-".join(str(p) for p in parts))
    return normalize_order_ref("ibkr-order")

def _build_order_ref(
    *,
    order_ref: str | None = None,
    intent_key: str | None = None,
    user_id: str | None = None,
    broker: str | None = None,
    account_id: str | None = None,
    strategy_id: str | None = None,
    symbol: str | None = None,
    side: str | None = None,
    **kwargs,
) -> str:
    return generate_order_ref(
        order_ref=order_ref,
        intent_key=intent_key,
        user_id=user_id,
        broker=broker,
        account_id=account_id,
        strategy_id=strategy_id,
        symbol=symbol,
        side=side,
        **kwargs,
    )

def send_ibkr_test_order(
    api_key: str,
    api_secret: str,
    symbol: str,
    side: str,
    quantity: float,
    order_ref: str | None = None,
) -> dict[str, Any]:
    # Validación mínima local
    if not api_key or len(str(api_key).strip()) < 8:
        raise RuntimeError("ibkr_input_error: api_key missing or too short")
    if not api_secret or len(str(api_secret).strip()) < 8:
        raise RuntimeError("ibkr_input_error: api_secret missing or too short")
    if not symbol or not str(symbol).strip():
        raise RuntimeError("ibkr_input_error: symbol missing")
    if not isinstance(quantity, (int, float)) or quantity <= 0:
        raise RuntimeError("ibkr_input_error: quantity must be > 0")
    if not str(order_ref or "").strip():
        raise RuntimeError("kernel_dispatch_guard: missing order_ref")

    # Optional external bridge mode for teams that expose an IBKR paper gateway.
    if settings.IBKR_BRIDGE_BASE_URL:
        payload = {
            "symbol": symbol.upper(),
            "side": side.upper(),
            "qty": quantity,
            "order_ref": order_ref,
            "mode": "paper_test",
        }
        payload_raw = json.dumps(payload, separators=(",", ":"))
        signature = hmac.new(
            api_secret.encode("utf-8"),
            payload_raw.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        headers = {
            "X-API-KEY": api_key,
            "X-SIGNATURE": signature,
            "Content-Type": "application/json",
        }
        url = f"{settings.IBKR_BRIDGE_BASE_URL.rstrip('/')}/ibkr/paper/test-order"
        response = _post_bridge(url, payload_raw=payload_raw, headers=headers, timeout=12)
        if response.status_code >= 400:
            raise RuntimeError(_format_bridge_error(response.status_code, response.text))
        return {"ok": True, "mode": "bridge", "order_ref": order_ref}

    # Safe fallback: deterministic local simulation (no money movement).
    return {
        "status": "accepted",
        "order_ref": order_ref,
        "mode": "ibkr_simulated_execution"
    }


def get_ibkr_account_status(
    api_key: str,
    api_secret: str,
) -> dict[str, Any]:
    if len(api_key or "") < 8:
        raise RuntimeError("ibkr_input_error field=api_key reason=too_short")
    if len(api_secret or "") < 8:
        raise RuntimeError("ibkr_input_error field=api_secret reason=too_short")

    if settings.IBKR_BRIDGE_BASE_URL:
        payload = {"mode": "paper_status"}
        payload_raw = json.dumps(payload, separators=(",", ":"))
        signature = hmac.new(
            api_secret.encode("utf-8"),
            payload_raw.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        headers = {
            "X-API-KEY": api_key,
            "X-SIGNATURE": signature,
            "Content-Type": "application/json",
        }
        url = f"{settings.IBKR_BRIDGE_BASE_URL.rstrip('/')}/ibkr/paper/account-status"
        response = _post_bridge(url, payload_raw=payload_raw, headers=headers, timeout=12)
        if response.status_code >= 400:
            raise RuntimeError(_format_bridge_error(response.status_code, response.text))
        body = response.json()
        body["mode"] = "bridge"
        return body

    # Safe fallback while bridge is not configured.
    return {
        "mode": "simulated",
        "account_id": "paper-simulated",
        "currency": "USD",
        "can_trade": True,
        "cash": None,
        "buying_power": None,
        "net_liquidation": None,
        "positions": [],
        "open_orders": [],
    }
