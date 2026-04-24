from __future__ import annotations

import hashlib
import hmac
import time
from urllib.parse import urlencode

import requests

from apps.api.app.core.config import settings


def ping_binance_credentials(api_key: str, api_secret: str) -> dict:
    if not settings.BINANCE_GATEWAY_FALLBACK_DIRECT:
        return {
            "success": False,
            "exchange": "BINANCE",
            "can_authenticate": False,
            "detail": "binance_direct_ping_disabled",
        }
    base_url = settings.BINANCE_TESTNET_BASE_URL.rstrip("/")
    params = {"timestamp": int(time.time() * 1000)}
    query_string = urlencode(params)
    signature = hmac.new(
        api_secret.encode("utf-8"),
        query_string.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    response = requests.get(
        f"{base_url}/api/v3/account",
        params={**params, "signature": signature},
        headers={"X-MBX-APIKEY": api_key},
        timeout=10,
    )
    if response.ok:
        return {
            "success": True,
            "exchange": "BINANCE",
            "can_authenticate": True,
            "detail": None,
        }
    try:
        payload = response.json()
        detail = payload.get("msg") or payload.get("message") or response.text
    except Exception:
        detail = response.text
    return {
        "success": False,
        "exchange": "BINANCE",
        "can_authenticate": False,
        "detail": str(detail or "Binance authentication failed").strip()[:300],
    }
