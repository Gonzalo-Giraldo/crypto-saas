import hashlib
import hmac
import time
from urllib.parse import urlencode

import requests

from apps.api.app.core.config import settings


def send_test_order(
    api_key: str,
    api_secret: str,
    symbol: str,
    side: str,
    quantity: float,
    order_type: str = "MARKET",
):
    endpoint = "/api/v3/order/test"
    base_url = settings.BINANCE_TESTNET_BASE_URL.rstrip("/")

    params = {
        "symbol": symbol.upper(),
        "side": side.upper(),
        "type": order_type.upper(),
        "quantity": quantity,
        "timestamp": int(time.time() * 1000),
    }

    query = urlencode(params)
    signature = hmac.new(
        api_secret.encode("utf-8"),
        query.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    signed_query = f"{query}&signature={signature}"
    url = f"{base_url}{endpoint}?{signed_query}"
    headers = {"X-MBX-APIKEY": api_key}

    response = requests.post(url, headers=headers, timeout=10)
    if response.status_code >= 400:
        detail = response.text
        raise RuntimeError(f"Binance testnet error {response.status_code}: {detail}")

    return {"ok": True}
