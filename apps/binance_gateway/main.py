import hashlib
import hmac
import time
from urllib.parse import urlencode
import os
import threading

import requests
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

app = FastAPI()

INTERNAL_TOKEN = os.getenv("BINANCE_GATEWAY_TOKEN", "")
BINANCE_BASE = os.getenv("BINANCE_BASE_URL", "https://testnet.binance.vision").rstrip("/")
REQUEST_TIMEOUT_SECONDS = int(os.getenv("BINANCE_GATEWAY_TIMEOUT_SECONDS", "12"))
HEALTHZ_CHECK_BINANCE = os.getenv("BINANCE_GATEWAY_HEALTHZ_CHECK_BINANCE", "false").lower() == "true"
RATE_LIMIT_PER_MIN = int(os.getenv("BINANCE_GATEWAY_RATE_LIMIT_PER_MIN", "60"))

_RATE_LOCK = threading.Lock()
_rate_state: dict[str, tuple[int, int]] = {}


class BinanceTestOrderIn(BaseModel):
    api_key: str
    api_secret: str
    symbol: str
    side: str
    qty: float


@app.get("/healthz")
def healthz():
    if not HEALTHZ_CHECK_BINANCE:
        return {"status": "ok", "binance_check": "skipped"}

    try:
        r = requests.get(f"{BINANCE_BASE}/api/v3/time", timeout=max(2, REQUEST_TIMEOUT_SECONDS))
        ok = r.status_code == 200
        return {"status": "ok" if ok else "degraded", "binance_check": r.status_code}
    except Exception:
        return {"status": "degraded", "binance_check": "unreachable"}


@app.post("/binance/test-order")
def binance_test_order(payload: BinanceTestOrderIn, x_internal_token: str = Header(default="")):
    if not INTERNAL_TOKEN or x_internal_token != INTERNAL_TOKEN:
        raise HTTPException(status_code=403, detail="forbidden")
    _enforce_rate_limit(x_internal_token)

    params = {
        "symbol": payload.symbol.upper(),
        "side": payload.side.upper(),
        "type": "MARKET",
        "quantity": payload.qty,
        "timestamp": int(time.time() * 1000),
    }
    query = urlencode(params)
    signature = hmac.new(
        payload.api_secret.encode("utf-8"),
        query.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    url = f"{BINANCE_BASE}/api/v3/order/test?{query}&signature={signature}"
    headers = {"X-MBX-APIKEY": payload.api_key}
    r = requests.post(url, headers=headers, timeout=max(3, REQUEST_TIMEOUT_SECONDS))

    if r.status_code >= 400:
        binance_code = None
        try:
            body = r.json()
            binance_code = body.get("code")
        except Exception:
            pass
        # Avoid leaking upstream payloads; keep a concise diagnostic.
        detail = f"binance_upstream_error status={r.status_code}"
        if binance_code is not None:
            detail += f" code={binance_code}"
        raise HTTPException(status_code=502, detail=detail)

    return {"ok": True, "mode": "gateway_test_order"}


def _enforce_rate_limit(key: str) -> None:
    if RATE_LIMIT_PER_MIN <= 0:
        return
    now_minute = int(time.time() // 60)
    with _RATE_LOCK:
        minute, count = _rate_state.get(key, (now_minute, 0))
        if minute != now_minute:
            minute, count = now_minute, 0
        count += 1
        _rate_state[key] = (minute, count)
        if count > RATE_LIMIT_PER_MIN:
            raise HTTPException(status_code=429, detail="rate_limit_exceeded")
