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
    client_order_id: str | None = None


class BinanceAccountStatusIn(BaseModel):
    api_key: str
    api_secret: str


class BinanceTicker24hIn(BaseModel):
    symbols: list[str] | None = None
    limit: int = 200


class BinanceKlinesIn(BaseModel):
    symbol: str
    interval: str = "1h"
    limit: int = 120


class BinanceExchangeInfoIn(BaseModel):
    symbols: list[str]


class BinanceTickerPriceIn(BaseModel):
    symbol: str


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
    if payload.client_order_id:
        params["newClientOrderId"] = str(payload.client_order_id)[:36]
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


@app.post("/binance/account-status")
def binance_account_status(payload: BinanceAccountStatusIn, x_internal_token: str = Header(default="")):
    if not INTERNAL_TOKEN or x_internal_token != INTERNAL_TOKEN:
        raise HTTPException(status_code=403, detail="forbidden")
    _enforce_rate_limit(x_internal_token)

    params = {
        "timestamp": int(time.time() * 1000),
    }
    query = urlencode(params)
    signature = hmac.new(
        payload.api_secret.encode("utf-8"),
        query.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    url = f"{BINANCE_BASE}/api/v3/account?{query}&signature={signature}"
    headers = {"X-MBX-APIKEY": payload.api_key}
    r = requests.get(url, headers=headers, timeout=max(3, REQUEST_TIMEOUT_SECONDS))
    if r.status_code >= 400:
        binance_code = None
        try:
            body = r.json()
            binance_code = body.get("code")
        except Exception:
            pass
        detail = f"binance_upstream_error status={r.status_code}"
        if binance_code is not None:
            detail += f" code={binance_code}"
        raise HTTPException(status_code=502, detail=detail)
    return r.json()


@app.post("/binance/ticker-24hr")
def binance_ticker_24hr(payload: BinanceTicker24hIn, x_internal_token: str = Header(default="")):
    if not INTERNAL_TOKEN or x_internal_token != INTERNAL_TOKEN:
        raise HTTPException(status_code=403, detail="forbidden")
    _enforce_rate_limit(x_internal_token)

    url = f"{BINANCE_BASE}/api/v3/ticker/24hr"
    r = requests.get(url, timeout=max(3, REQUEST_TIMEOUT_SECONDS))
    if r.status_code >= 400:
        detail = f"binance_upstream_error status={r.status_code}"
        raise HTTPException(status_code=502, detail=detail)
    data = r.json()
    if not isinstance(data, list):
        raise HTTPException(status_code=502, detail="invalid_ticker_payload")

    symbols_filter = {str(s).upper().strip() for s in (payload.symbols or []) if str(s).strip()}
    limit = max(1, min(int(payload.limit), 1000))
    out: list[dict] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        symbol = str(item.get("symbol") or "").upper().strip()
        if not symbol:
            continue
        if symbols_filter and symbol not in symbols_filter:
            continue
        out.append(item)
        if len(out) >= limit:
            break
    return {"rows": out, "count": len(out), "mode": "gateway_ticker_24hr"}


@app.post("/binance/klines")
def binance_klines(payload: BinanceKlinesIn, x_internal_token: str = Header(default="")):
    if not INTERNAL_TOKEN or x_internal_token != INTERNAL_TOKEN:
        raise HTTPException(status_code=403, detail="forbidden")
    _enforce_rate_limit(x_internal_token)

    symbol = str(payload.symbol or "").upper().strip()
    interval = str(payload.interval or "1h").strip()
    limit = max(10, min(int(payload.limit or 120), 1000))
    if not symbol:
        raise HTTPException(status_code=400, detail="symbol_required")
    url = f"{BINANCE_BASE}/api/v3/klines?{urlencode({'symbol': symbol, 'interval': interval, 'limit': limit})}"
    r = requests.get(url, timeout=max(3, REQUEST_TIMEOUT_SECONDS))
    if r.status_code >= 400:
        detail = f"binance_upstream_error status={r.status_code}"
        raise HTTPException(status_code=502, detail=detail)
    data = r.json()
    if not isinstance(data, list):
        raise HTTPException(status_code=502, detail="invalid_klines_payload")
    rows = [x for x in data if isinstance(x, list)]
    return {"rows": rows, "count": len(rows), "mode": "gateway_klines"}


@app.post("/binance/exchange-info")
def binance_exchange_info(payload: BinanceExchangeInfoIn, x_internal_token: str = Header(default="")):
    if not INTERNAL_TOKEN or x_internal_token != INTERNAL_TOKEN:
        raise HTTPException(status_code=403, detail="forbidden")
    _enforce_rate_limit(x_internal_token)

    symbols = sorted({str(s).upper().strip() for s in (payload.symbols or []) if str(s).strip()})
    if not symbols:
        raise HTTPException(status_code=400, detail="symbols_required")
    query = urlencode({"symbols": str(symbols).replace("'", '"')})
    url = f"{BINANCE_BASE}/api/v3/exchangeInfo?{query}"
    r = requests.get(url, timeout=max(3, REQUEST_TIMEOUT_SECONDS))
    if r.status_code >= 400:
        detail = f"binance_upstream_error status={r.status_code}"
        raise HTTPException(status_code=502, detail=detail)
    data = r.json()
    rows = data.get("symbols") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        raise HTTPException(status_code=502, detail="invalid_exchange_info_payload")
    return {"symbols": rows, "count": len(rows), "mode": "gateway_exchange_info"}


@app.post("/binance/ticker-price")
def binance_ticker_price(payload: BinanceTickerPriceIn, x_internal_token: str = Header(default="")):
    if not INTERNAL_TOKEN or x_internal_token != INTERNAL_TOKEN:
        raise HTTPException(status_code=403, detail="forbidden")
    _enforce_rate_limit(x_internal_token)

    symbol = str(payload.symbol or "").upper().strip()
    if not symbol:
        raise HTTPException(status_code=400, detail="symbol_required")
    query = urlencode({"symbol": symbol})
    url = f"{BINANCE_BASE}/api/v3/ticker/price?{query}"
    r = requests.get(url, timeout=max(3, REQUEST_TIMEOUT_SECONDS))
    if r.status_code >= 400:
        detail = f"binance_upstream_error status={r.status_code}"
        raise HTTPException(status_code=502, detail=detail)
    data = r.json()
    if not isinstance(data, dict):
        raise HTTPException(status_code=502, detail="invalid_ticker_price_payload")
    return {"row": data, "mode": "gateway_ticker_price"}


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
