import hashlib
import hmac
import json
from typing import Any

import requests

from apps.api.app.core.config import settings


def _validate_inputs(api_key: str, api_secret: str, symbol: str, quantity: float):
    if len(api_key or "") < 8:
        raise RuntimeError("IBKR api_key seems invalid (too short)")
    if len(api_secret or "") < 8:
        raise RuntimeError("IBKR api_secret seems invalid (too short)")
    if not symbol or not symbol.isalnum():
        raise RuntimeError("IBKR symbol must be alphanumeric (e.g. AAPL)")
    if quantity <= 0:
        raise RuntimeError("IBKR quantity must be > 0")


def _build_order_ref(api_key: str, symbol: str, side: str, quantity: float) -> str:
    material = f"{api_key}|{symbol.upper()}|{side.upper()}|{quantity}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


def send_ibkr_test_order(
    api_key: str,
    api_secret: str,
    symbol: str,
    side: str,
    quantity: float,
) -> dict[str, Any]:
    _validate_inputs(api_key=api_key, api_secret=api_secret, symbol=symbol, quantity=quantity)
    order_ref = _build_order_ref(api_key=api_key, symbol=symbol, side=side, quantity=quantity)

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
        response = requests.post(url, data=payload_raw, headers=headers, timeout=12)
        if response.status_code >= 400:
            raise RuntimeError(f"IBKR bridge error {response.status_code}: {response.text}")
        return {"ok": True, "mode": "bridge", "order_ref": order_ref}

    # Safe fallback: deterministic local simulation (no money movement).
    return {"ok": True, "mode": "simulated", "order_ref": order_ref}
