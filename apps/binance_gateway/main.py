import hashlib
import hmac
import time
from urllib.parse import urlencode
import os

import requests
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

app = FastAPI()

INTERNAL_TOKEN = os.getenv("BINANCE_GATEWAY_TOKEN", "")
BINANCE_BASE = os.getenv("BINANCE_BASE_URL", "https://testnet.binance.vision").rstrip("/")


class BinanceTestOrderIn(BaseModel):
    api_key: str
    api_secret: str
    symbol: str
    side: str
    qty: float


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.post("/binance/test-order")
def binance_test_order(payload: BinanceTestOrderIn, x_internal_token: str = Header(default="")):
    if not INTERNAL_TOKEN or x_internal_token != INTERNAL_TOKEN:
        raise HTTPException(status_code=403, detail="forbidden")

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
    r = requests.post(url, headers=headers, timeout=12)

    if r.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"binance_error_{r.status_code}: {r.text}")

    return {"ok": True, "mode": "gateway_test_order"}
