"""
IBKR Client Transport Module
---------------------------
This module provides the explicit client seam for Interactive Brokers (IBKR) lifecycle operations.
Unlike Binance, there is no gateway abstraction for IBKR in this project. All transport and protocol
handling for IBKR order operations will be implemented directly in this module.

This groundwork provides placeholder functions for the main IBKR order lifecycle actions. These are
not yet implemented or wired to any adapter or runtime logic.
"""

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
    Cancel an order on IBKR. This is a placeholder for the future transport implementation.
    """
    raise NotImplementedError("IBKR cancel_order is not yet implemented.")
    code = _extract_bridge_code(body_text)
    if code:
        detail += f" code={code}"
    return detail


def _post_bridge(url: str, *, payload_raw: str, headers: dict, timeout: int = 12) -> requests.Response:
    try:
        return requests.post(url, data=payload_raw, headers=headers, timeout=timeout)
    except requests.RequestException:
        raise RuntimeError("ibkr_upstream_unreachable")


def send_ibkr_test_order(
    api_key: str,
    api_secret: str,
    symbol: str,
    side: str,
    quantity: float,
    order_ref: str | None = None,
) -> dict[str, Any]:
    _validate_inputs(api_key=api_key, api_secret=api_secret, symbol=symbol, quantity=quantity)
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
    return {"ok": True, "mode": "simulated", "order_ref": order_ref}


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
