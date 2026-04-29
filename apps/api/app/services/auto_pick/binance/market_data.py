from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any


_GATEWAY_BASE_URL_ENV = "BINANCE_GATEWAY_BASE_URL"
_GATEWAY_TOKEN_ENV = "BINANCE_GATEWAY_TOKEN"


def _gateway_base_url() -> str:
    base_url = str(os.environ.get(_GATEWAY_BASE_URL_ENV) or "").strip().rstrip("/")
    if not base_url:
        raise ValueError("binance_gateway_base_url_required")
    return base_url


def _gateway_token() -> str:
    token = str(os.environ.get(_GATEWAY_TOKEN_ENV) or "").strip()
    if not token:
        raise ValueError("binance_gateway_token_required")
    return token


def _post_gateway_json(path: str, payload: dict[str, Any], *, timeout_seconds: int = 15) -> dict[str, Any]:
    url = f"{_gateway_base_url()}{path}"
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        method="POST",
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-Internal-Token": _gateway_token(),
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
            raw = resp.read().decode("utf-8")
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
        raise RuntimeError("binance_gateway_request_failed") from exc

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("binance_gateway_invalid_json") from exc

    if not isinstance(parsed, dict):
        raise RuntimeError("binance_gateway_response_must_be_dict")
    return parsed


def _extract_rows(response: dict[str, Any]) -> list:
    rows = response.get("rows")
    if not isinstance(rows, list):
        raise RuntimeError("binance_gateway_rows_required")
    return rows


def fetch_ticker_24h_rows() -> list[dict[str, Any]]:
    try:
        response = _post_gateway_json("/binance/ticker-24hr", {"limit": 500})
        rows = _extract_rows(response)
    except Exception:
        return []
    return [row for row in rows if isinstance(row, dict)]


def fetch_klines(
    symbol: str,
    interval: str,
    limit: int,
    start_time_ms: int | None = None,
    end_time_ms: int | None = None,
) -> list[list]:
    symbol_norm = str(symbol or "").upper().strip()
    interval_norm = str(interval or "").strip()
    if not symbol_norm:
        raise ValueError("symbol_required")
    if not interval_norm:
        raise ValueError("interval_required")

    payload: dict[str, Any] = {
        "symbol": symbol_norm,
        "interval": interval_norm,
        "limit": int(limit),
    }
    if start_time_ms is not None:
        payload["start_time_ms"] = int(start_time_ms)
    if end_time_ms is not None:
        payload["end_time_ms"] = int(end_time_ms)

    try:
        response = _post_gateway_json("/binance/klines", payload)
        rows = _extract_rows(response)
    except Exception:
        return []
    return [row for row in rows if isinstance(row, list)]


def fetch_1h_klines(symbol: str, limit: int | None = None) -> list[list]:
    return fetch_klines(symbol=symbol, interval="1h", limit=int(limit or 120))


def fetch_15m_klines(symbol: str, limit: int = 96) -> list[list]:
    return fetch_klines(symbol=symbol, interval="15m", limit=int(limit))
