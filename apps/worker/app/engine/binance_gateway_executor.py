from __future__ import annotations

from typing import Any, Callable

import requests

from apps.api.app.core.config import settings


_SENSITIVE_KEYS = {
    "api_key",
    "apikey",
    "apiSecret",
    "api_secret",
    "secret",
    "signature",
    "DATABASE_URL",
    "database_url",
}


_ALLOWED_FUTURES_ORDER_TYPES = {
    "MARKET",
    "STOP_MARKET",
    "TAKE_PROFIT_MARKET",
}


def _gateway_order_url() -> str:
    base = str(getattr(settings, "BINANCE_GATEWAY_BASE_URL", "") or "").rstrip()
    if not base:
        raise RuntimeError("BINANCE_GATEWAY_BASE_URL_required")
    return f"{base.rstrip('/')}/binance/order"


def _gateway_algo_order_url() -> str:
    base = str(getattr(settings, "BINANCE_GATEWAY_BASE_URL", "") or "").rstrip()
    if not base:
        raise RuntimeError("BINANCE_GATEWAY_BASE_URL_required")
    return f"{base.rstrip('/')}/binance/algo-order"

def _gateway_algo_order_status_url() -> str:
    base = str(getattr(settings, "BINANCE_GATEWAY_BASE_URL", "") or "").rstrip()
    if not base:
        raise RuntimeError("BINANCE_GATEWAY_BASE_URL_required")
    return f"{base.rstrip('/')}/binance/algo-order-status"

def sanitize_order_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}

    sensitive_lower = {key.lower() for key in _SENSITIVE_KEYS}
    sanitized: dict[str, Any] = {}

    for key, value in payload.items():
        if str(key).lower() in sensitive_lower:
            sanitized[key] = "[REDACTED]"
        else:
            sanitized[key] = value

    return sanitized


def validate_futures_order_payload(order_payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(order_payload, dict):
        raise ValueError("order_payload_must_be_dict")

    market = str(order_payload.get("market") or "").upper().strip()
    if market != "FUTURES":
        raise ValueError("market_must_be_FUTURES")

    symbol = str(order_payload.get("symbol") or "").upper().strip()
    if not symbol:
        raise ValueError("symbol_required")

    side = str(order_payload.get("side") or "").upper().strip()
    if side not in {"BUY", "SELL"}:
        raise ValueError("side_must_be_BUY_or_SELL")

    order_type = str(order_payload.get("type") or "").upper().strip()
    if order_type not in _ALLOWED_FUTURES_ORDER_TYPES:
        raise ValueError("unsupported_futures_order_type")

    qty = order_payload.get("quantity")
    if qty is None:
        raise ValueError("quantity_required")

    if order_type in {"STOP_MARKET", "TAKE_PROFIT_MARKET"}:
        if "stopPrice" not in order_payload or order_payload.get("stopPrice") is None:
            raise ValueError("stopPrice_required_for_trigger_order")
        if order_payload.get("reduceOnly") is not True:
            raise ValueError("reduceOnly_true_required_for_exit_order")

    return {
        **order_payload,
        "market": market,
        "symbol": symbol,
        "side": side,
        "type": order_type,
    }


def send_order_via_gateway(
    order_payload: dict[str, Any],
    *,
    post: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    try:
        safe_payload = validate_futures_order_payload(order_payload)
        post_callable = post or requests.post

        target_url = (
            _gateway_order_url()
            if safe_payload["type"] == "MARKET"
            else _gateway_algo_order_url()
        )

        response = post_callable(
            target_url,
            json=safe_payload,
            timeout=max(3, int(settings.BINANCE_GATEWAY_TIMEOUT_SECONDS)),
        )
        response.raise_for_status()

        body = response.json()
        if not isinstance(body, dict):
            return {
                "status": "ERROR",
                "error": "invalid_gateway_json",
                "safe_order_payload": sanitize_order_payload(safe_payload),
            }

        return body

    except requests.exceptions.ReadTimeout:
        return {
            "status": "TIMEOUT",
            "error": "gateway_read_timeout",
            "safe_order_payload": sanitize_order_payload(order_payload),
        }

    except Exception as exc:
        return {
            "status": "ERROR",
            "error": str(exc),
            "safe_order_payload": sanitize_order_payload(order_payload),
        }

def fetch_algo_order_status_via_gateway(
    *,
    api_key: str,
    api_secret: str,
    symbol: str,
    algo_id: int | None = None,
    client_algo_id: str | None = None,
    post: Callable[..., Any] | None = None,
) -> dict[str, Any]:

    has_algo_id = algo_id is not None
    has_client_algo_id = bool(str(client_algo_id or "").strip())

    if has_algo_id == has_client_algo_id:
        raise ValueError("exactly_one_algo_identifier_required")

    symbol_norm = str(symbol or "").upper().strip()
    if not symbol_norm:
        raise ValueError("symbol_required")

    payload = {
        "api_key": api_key,
        "api_secret": api_secret,
        "symbol": symbol_norm,
    }

    if has_algo_id:
        payload["algoId"] = algo_id
    else:
        payload["clientAlgoId"] = str(client_algo_id).strip()

    try:
        post_callable = post or requests.post

        response = post_callable(
            _gateway_algo_order_status_url(),
            json=payload,
            timeout=max(3, int(settings.BINANCE_GATEWAY_TIMEOUT_SECONDS)),
        )

        response.raise_for_status()

        body = response.json()

        if not isinstance(body, dict):
            return {
                "status": "ERROR",
                "error": "invalid_gateway_json",
            }

        return {
            "status": "OK",
            "response": body,
        }

    except requests.exceptions.ReadTimeout:
        return {
            "status": "TIMEOUT",
            "error": "gateway_read_timeout",
        }

    except Exception as exc:
        return {
            "status": "ERROR",
            "error": str(exc),
        }
