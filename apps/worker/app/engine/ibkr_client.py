import hashlib
import hmac
import json
import re
from typing import Any

import requests

from apps.api.app.core.config import settings


def _validate_inputs(api_key: str, api_secret: str, symbol: str, quantity: float):
    if len(api_key or "") < 8:
        raise RuntimeError("ibkr_input_error field=api_key reason=too_short")
    if len(api_secret or "") < 8:
        raise RuntimeError("ibkr_input_error field=api_secret reason=too_short")
    if not symbol or not symbol.isalnum():
        raise RuntimeError("ibkr_input_error field=symbol reason=non_alnum")
    if quantity <= 0:
        raise RuntimeError("ibkr_input_error field=quantity reason=non_positive")


def _build_order_ref(api_key: str, symbol: str, side: str, quantity: float) -> str:
    material = f"{api_key}|{symbol.upper()}|{side.upper()}|{quantity}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


def _extract_bridge_code(text: str) -> str | None:
    msg = str(text or "")
    m = re.search(r"\bcode=([A-Za-z0-9_\-]+)", msg)
    if m:
        return m.group(1)
    m = re.search(r'"code"\s*:\s*"?([A-Za-z0-9_\-]+)"?', msg)
    if m:
        return m.group(1)
    return None


def _format_bridge_error(status_code: int, body_text: str) -> str:
    detail = f"ibkr_upstream_error status={int(status_code)}"
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
