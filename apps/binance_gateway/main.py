import hashlib
import hmac
import time
from urllib.parse import urlencode
import os
import threading

import requests
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
import inspect
import json
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

app = FastAPI()

INTERNAL_TOKEN = os.getenv("BINANCE_GATEWAY_TOKEN", "")
_legacy_base = os.getenv("BINANCE_BASE_URL", "").rstrip("/")
BINANCE_SPOT_BASE = (
    os.getenv("BINANCE_SPOT_BASE_URL")
    or os.getenv("BINANCE_TESTNET_BASE_URL")
    or _legacy_base
    or "https://testnet.binance.vision"
).rstrip("/")
BINANCE_FUTURES_BASE = os.getenv("BINANCE_FUTURES_BASE_URL", "https://testnet.binancefuture.com").rstrip("/")
REQUEST_TIMEOUT_SECONDS = int(os.getenv("BINANCE_GATEWAY_TIMEOUT_SECONDS", "12"))
HEALTHZ_CHECK_BINANCE = os.getenv("BINANCE_GATEWAY_HEALTHZ_CHECK_BINANCE", "false").lower() == "true"
RATE_LIMIT_PER_MIN = int(os.getenv("BINANCE_GATEWAY_RATE_LIMIT_PER_MIN", "60"))

_RATE_LOCK = threading.Lock()
_rate_state: dict[str, tuple[int, int]] = {}
# Circuit breaker state
_CIRCUIT_LOCK = threading.Lock()
_circuit_state = {
    "fail_count": 0,
    "open_until": 0.0,
}

CIRCUIT_BREAKER_THRESHOLD = int(os.getenv("BINANCE_CB_THRESHOLD", "5"))
CIRCUIT_BREAKER_COOLDOWN_SEC = int(os.getenv("BINANCE_CB_COOLDOWN", "10"))



class BinanceTestOrderIn(BaseModel):
    api_key: str
    api_secret: str
    symbol: str
    side: str
    qty: float
    client_order_id: str | None = None
    market: str | None = None


class BinanceAccountStatusIn(BaseModel):
    api_key: str
    api_secret: str


class BinanceOrderStatusIn(BaseModel):
    api_key: str
    api_secret: str
    symbol: str
    orig_client_order_id: str
    market: str | None = None

class BinanceMyTradesIn(BaseModel):
    api_key: str
    api_secret: str
    symbol: str
    market: str | None = None

class BinanceTicker24hIn(BaseModel):
    symbols: list[str] | None = None
    limit: int = 200
    market: str | None = None


class BinanceKlinesIn(BaseModel):
    symbol: str
    interval: str = "1h"
    limit: int = 120
    market: str | None = None
    start_time_ms: int | None = None
    end_time_ms: int | None = None


class BinanceExchangeInfoIn(BaseModel):
    symbols: list[str]
    market: str | None = None


class BinanceTickerPriceIn(BaseModel):
    symbol: str
    market: str | None = None


def _resolve_market(value: str | None) -> str:
    market = str(value or "SPOT").upper().strip()
    if market not in {"SPOT", "FUTURES"}:
        raise HTTPException(status_code=400, detail="market must be SPOT or FUTURES")
    return market


def _base_url_for_market(market: str) -> str:
    return BINANCE_FUTURES_BASE if market == "FUTURES" else BINANCE_SPOT_BASE



def _sanitize_upstream_log_url(url: object) -> str:
    raw = str(url)
    try:
        parts = urlsplit(raw)
        filtered_query = urlencode(
            [
                (key, value)
                for key, value in parse_qsl(parts.query, keep_blank_values=True)
                if key.lower() not in {"api_key", "apikey", "signature"}
            ]
        )
        return urlunsplit((parts.scheme, parts.netloc, parts.path, filtered_query, parts.fragment))
    except Exception:
        return "<unparseable_url_redacted>"


def _request_upstream(*args, **kwargs):
    now = time.time()
    with _CIRCUIT_LOCK:
        if _circuit_state["open_until"] > now:
            raise HTTPException(
                status_code=503,
                detail="binance_circuit_open",
            )

    timestamp = now
    started = time.perf_counter()
    status_code = None
    method = kwargs.get("method")
    url = kwargs.get("url")

    try:
        bound = inspect.signature(_request_upstream_raw).bind_partial(*args, **kwargs)
        if method is None:
            method = bound.arguments.get("method")
        if url is None:
            url = bound.arguments.get("url")
    except Exception:
        if args and method is None:
            method = args[0]
        if len(args) > 1 and url is None:
            url = args[1]

    try:
        result = _request_upstream_raw(*args, **kwargs)

        if hasattr(result, "status_code"):
            status_code = result.status_code
        elif isinstance(result, dict):
            status_code = result.get("status_code") or result.get("status")

        if isinstance(status_code, int) and status_code >= 400:
            with _CIRCUIT_LOCK:
                _circuit_state["fail_count"] += 1
                if _circuit_state["fail_count"] >= CIRCUIT_BREAKER_THRESHOLD:
                    _circuit_state["open_until"] = time.time() + CIRCUIT_BREAKER_COOLDOWN_SEC
        else:
            with _CIRCUIT_LOCK:
                _circuit_state["fail_count"] = 0

        return result
    except Exception as exc:
        status_code = getattr(exc, "code", None) or getattr(exc, "status", None)

        with _CIRCUIT_LOCK:
            _circuit_state["fail_count"] += 1
            if _circuit_state["fail_count"] >= CIRCUIT_BREAKER_THRESHOLD:
                _circuit_state["open_until"] = time.time() + CIRCUIT_BREAKER_COOLDOWN_SEC

        raise
    finally:
        duration_ms = round((time.perf_counter() - started) * 1000, 3)
        print(
            json.dumps(
                {
                    "event": "binance_gateway_upstream_request",
                    "method": str(method or "GET").upper(),
                    "url": _sanitize_upstream_log_url(url),
                    "timestamp": timestamp,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                },
                sort_keys=True,
            ),
            flush=True,
        )


def _request_upstream_raw(method: str, url: str, **kwargs) -> requests.Response:
    try:
        return requests.request(method=method.upper(), url=url, **kwargs)
    except requests.RequestException:
        raise HTTPException(status_code=502, detail="binance_upstream_unreachable")


def _raise_upstream_http_error(response: requests.Response) -> None:
    binance_code = None
    try:
        body = response.json()
        if isinstance(body, dict):
            binance_code = body.get("code")
    except Exception:
        pass
    detail = f"binance_upstream_error status={response.status_code}"
    if binance_code is not None:
        detail += f" code={binance_code}"
    raise HTTPException(status_code=502, detail=detail)


def _request_upstream_json(method: str, url: str, timeout: int) -> object:
    response = _request_upstream(method, url, timeout=timeout)
    if response.status_code >= 400:
        _raise_upstream_http_error(response)
    return response.json()


def _endpoint_weight(path: str) -> int:
    weights = {
        "/binance/order": 5,
        "/binance/test-order": 1,
        "/binance/ticker-price": 1,
        "/binance/klines": 2,
    }
    return int(weights.get(path, 1))


def _authorize_internal_request(x_internal_token: str, endpoint_path: str = "") -> None:
    if not INTERNAL_TOKEN or x_internal_token != INTERNAL_TOKEN:
        raise HTTPException(status_code=403, detail="forbidden")
    _enforce_rate_limit(x_internal_token, weight=_endpoint_weight(endpoint_path))


@app.get("/healthz")
def healthz():
    if not HEALTHZ_CHECK_BINANCE:
        return {"status": "ok", "binance_check": "skipped"}

    try:
        r = _request_upstream("GET", f"{BINANCE_SPOT_BASE}/api/v3/time", timeout=max(2, REQUEST_TIMEOUT_SECONDS))
        ok = r.status_code == 200
        return {"status": "ok" if ok else "degraded", "binance_check": r.status_code}
    except Exception:
        return {"status": "degraded", "binance_check": "unreachable"}




@app.post("/binance/order")
def binance_order(payload: BinanceTestOrderIn, x_internal_token: str = Header(default="")):
    _authorize_internal_request(x_internal_token, endpoint_path="/binance/order")

    market = _resolve_market(payload.market)
    base_url = _base_url_for_market(market)
    endpoint = "/fapi/v1/order" if market == "FUTURES" else "/api/v3/order"

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

    url = f"{base_url}{endpoint}?{query}&signature={signature}"
    headers = {"X-MBX-APIKEY": payload.api_key}
    response = _request_upstream("POST", url, headers=headers, timeout=max(3, REQUEST_TIMEOUT_SECONDS))

    if response.status_code >= 400:
        _raise_upstream_http_error(response)

    data = response.json()
    if not isinstance(data, dict):
        raise HTTPException(status_code=502, detail="invalid_order_payload")

    return {"ok": True, "mode": f"gateway_order_{market.lower()}", "data": data}

@app.post("/binance/test-order")
def binance_test_order(payload: BinanceTestOrderIn, x_internal_token: str = Header(default="")):
    _authorize_internal_request(x_internal_token, endpoint_path="/binance/test-order")

    market = _resolve_market(payload.market)
    base_url = _base_url_for_market(market)
    if market == "FUTURES":
        endpoint = "/fapi/v1/order/test"
    else:
        endpoint = "/api/v3/order/test"

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

    url = f"{base_url}{endpoint}?{query}&signature={signature}"
    headers = {"X-MBX-APIKEY": payload.api_key}
    r = _request_upstream("POST", url, headers=headers, timeout=max(3, REQUEST_TIMEOUT_SECONDS))

    if r.status_code >= 400:
        _raise_upstream_http_error(r)

    return {"ok": True, "mode": f"gateway_test_order_{market.lower()}"}




class BinanceCancelOrderIn(BaseModel):
    api_key: str
    api_secret: str
    symbol: str
    orig_client_order_id: str
    market: str = "SPOT"


@app.post("/binance/cancel-order")
def binance_cancel_order(
    payload: BinanceCancelOrderIn,
    x_internal_token: str = Header(default="")
):
    _authorize_internal_request(x_internal_token)

    market = _resolve_market(payload.market)
    base_url = _base_url_for_market(market)
    endpoint = "/fapi/v1/order" if market == "FUTURES" else "/api/v3/order"

    params = {
        "symbol": payload.symbol.upper(),
        "origClientOrderId": payload.orig_client_order_id,
        "timestamp": int(time.time() * 1000),
    }
    query = urlencode(params)
    signature = hmac.new(
        payload.api_secret.encode("utf-8"),
        query.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    url = f"{base_url}{endpoint}?{query}&signature={signature}"
    headers = {"X-MBX-APIKEY": payload.api_key}
    response = _request_upstream("DELETE", url, headers=headers, timeout=max(3, REQUEST_TIMEOUT_SECONDS))
    if response.status_code >= 400:
        _raise_upstream_http_error(response)
    data = response.json()
    mode = f"gateway_cancel_order_{market.lower()}"
    return {"ok": True, "mode": mode, "data": data}

@app.post("/binance/order-status")
def binance_order_status(payload: BinanceOrderStatusIn, x_internal_token: str = Header(default="")):
    _authorize_internal_request(x_internal_token)

    market = _resolve_market(payload.market)
    base_url = _base_url_for_market(market)
    endpoint = "/fapi/v1/order" if market == "FUTURES" else "/api/v3/order"

    params = {
        "symbol": payload.symbol.upper(),
        "origClientOrderId": payload.orig_client_order_id,
        "timestamp": int(time.time() * 1000),
    }
    query = urlencode(params)
    signature = hmac.new(
        payload.api_secret.encode("utf-8"),
        query.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    url = f"{base_url}{endpoint}?{query}&signature={signature}"
    headers = {"X-MBX-APIKEY": payload.api_key}
    response = _request_upstream("GET", url, headers=headers, timeout=max(3, REQUEST_TIMEOUT_SECONDS))
    if response.status_code >= 400:
        _raise_upstream_http_error(response)
    data = response.json()
    if not isinstance(data, dict):
        raise HTTPException(status_code=502, detail="invalid_order_status_payload")
    return {"ok": True, "data": data, "mode": f"gateway_order_status_{market.lower()}"}

@app.post("/binance/my-trades")
def binance_my_trades(payload: BinanceMyTradesIn, x_internal_token: str = Header(default="")):
    _authorize_internal_request(x_internal_token)

    market = _resolve_market(payload.market)
    base_url = _base_url_for_market(market)
    endpoint = "/fapi/v1/userTrades" if market == "FUTURES" else "/api/v3/myTrades"

    params = {
        "symbol": payload.symbol.upper(),
        "timestamp": int(time.time() * 1000),
    }
    query = urlencode(params)
    signature = hmac.new(
        payload.api_secret.encode("utf-8"),
        query.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    url = f"{base_url}{endpoint}?{query}&signature={signature}"
    headers = {"X-MBX-APIKEY": payload.api_key}
    response = _request_upstream("GET", url, headers=headers, timeout=max(3, REQUEST_TIMEOUT_SECONDS))

    print("DEBUG /binance/my-trades status=", response.status_code)
    print("DEBUG /binance/my-trades body=", response.text)

    if response.status_code >= 400:
        _raise_upstream_http_error(response)

    data = response.json()
    if not isinstance(data, list):
        raise HTTPException(status_code=502, detail="binance_upstream_invalid_payload")

    return {"rows": data}

@app.post("/binance/account-status")
def binance_account_status(payload: BinanceAccountStatusIn, x_internal_token: str = Header(default="")):
    _authorize_internal_request(x_internal_token)

    params = {
        "timestamp": int(time.time() * 1000),
    }
    query = urlencode(params)
    signature = hmac.new(
        payload.api_secret.encode("utf-8"),
        query.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    url = f"{BINANCE_SPOT_BASE}/api/v3/account?{query}&signature={signature}"
    headers = {"X-MBX-APIKEY": payload.api_key}
    r = _request_upstream("GET", url, headers=headers, timeout=max(3, REQUEST_TIMEOUT_SECONDS))
    if r.status_code >= 400:
        _raise_upstream_http_error(r)
    return r.json()


@app.post("/binance/ticker-24hr")
def binance_ticker_24hr(payload: BinanceTicker24hIn, x_internal_token: str = Header(default="")):
    _authorize_internal_request(x_internal_token)

    market = _resolve_market(payload.market)
    if market == "FUTURES":
        url = f"{BINANCE_FUTURES_BASE}/fapi/v1/ticker/24hr"
    else:
        url = f"{BINANCE_SPOT_BASE}/api/v3/ticker/24hr"
    data = _request_upstream_json("GET", url, timeout=max(3, REQUEST_TIMEOUT_SECONDS))
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
    return {"rows": out, "count": len(out), "mode": f"gateway_ticker_24hr_{market.lower()}"}


@app.post("/binance/klines")
def binance_klines(payload: BinanceKlinesIn, x_internal_token: str = Header(default="")):
    _authorize_internal_request(x_internal_token, endpoint_path="/binance/klines")

    market = _resolve_market(payload.market)
    symbol = str(payload.symbol or "").upper().strip()
    interval = str(payload.interval or "1h").strip()
    limit = max(10, min(int(payload.limit or 120), 1000))
    if not symbol:
        raise HTTPException(status_code=400, detail="symbol_required")
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    if payload.start_time_ms is not None:
        params["startTime"] = int(payload.start_time_ms)
    if payload.end_time_ms is not None:
        params["endTime"] = int(payload.end_time_ms)

    if market == "FUTURES":
        url = f"{BINANCE_FUTURES_BASE}/fapi/v1/klines?{urlencode(params)}"
    else:
        url = f"{BINANCE_SPOT_BASE}/api/v3/klines?{urlencode(params)}"
    data = _request_upstream_json("GET", url, timeout=max(3, REQUEST_TIMEOUT_SECONDS))
    if not isinstance(data, list):
        raise HTTPException(status_code=502, detail="invalid_klines_payload")
    rows = [x for x in data if isinstance(x, list)]
    return {"rows": rows, "count": len(rows), "mode": f"gateway_klines_{market.lower()}"}


@app.post("/binance/exchange-info")
def binance_exchange_info(payload: BinanceExchangeInfoIn, x_internal_token: str = Header(default="")):
    _authorize_internal_request(x_internal_token)

    market = _resolve_market(payload.market)
    symbols = sorted({str(s).upper().strip() for s in (payload.symbols or []) if str(s).strip()})
    if not symbols:
        raise HTTPException(status_code=400, detail="symbols_required")
    query = urlencode({"symbols": str(symbols).replace("'", '"')})
    if market == "FUTURES":
        if len(symbols) == 1:
            url = f"{BINANCE_FUTURES_BASE}/fapi/v1/exchangeInfo?{urlencode({'symbol': symbols[0]})}"
        else:
            url = f"{BINANCE_FUTURES_BASE}/fapi/v1/exchangeInfo"
    else:
        url = f"{BINANCE_SPOT_BASE}/api/v3/exchangeInfo?{query}"
    data = _request_upstream_json("GET", url, timeout=max(3, REQUEST_TIMEOUT_SECONDS))
    rows = data.get("symbols") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        raise HTTPException(status_code=502, detail="invalid_exchange_info_payload")
    if market == "FUTURES":
        wanted = set(symbols)
        rows = [row for row in rows if str((row or {}).get("symbol") or "").upper() in wanted]
    return {"symbols": rows, "count": len(rows), "mode": f"gateway_exchange_info_{market.lower()}"}


@app.post("/binance/ticker-price")
def binance_ticker_price(payload: BinanceTickerPriceIn, x_internal_token: str = Header(default="")):
    _authorize_internal_request(x_internal_token, endpoint_path="/binance/ticker-price")

    market = _resolve_market(payload.market)
    symbol = str(payload.symbol or "").upper().strip()
    if not symbol:
        raise HTTPException(status_code=400, detail="symbol_required")
    query = urlencode({"symbol": symbol})
    if market == "FUTURES":
        url = f"{BINANCE_FUTURES_BASE}/fapi/v1/ticker/price?{query}"
    else:
        url = f"{BINANCE_SPOT_BASE}/api/v3/ticker/price?{query}"
    data = _request_upstream_json("GET", url, timeout=max(3, REQUEST_TIMEOUT_SECONDS))
    if not isinstance(data, dict):
        raise HTTPException(status_code=502, detail="invalid_ticker_price_payload")
    return {"row": data, "mode": f"gateway_ticker_price_{market.lower()}"}


def _enforce_rate_limit(key: str, weight: int = 1) -> None:
    if RATE_LIMIT_PER_MIN <= 0:
        return
    safe_weight = max(1, int(weight or 1))
    now_minute = int(time.time() // 60)
    with _RATE_LOCK:
        minute, used_weight = _rate_state.get(key, (now_minute, 0))
        if minute != now_minute:
            minute, used_weight = now_minute, 0
        next_weight = used_weight + safe_weight
        _rate_state[key] = (minute, next_weight)
        if next_weight > RATE_LIMIT_PER_MIN:
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "rate_limit_exceeded",
                    "limit_per_min": RATE_LIMIT_PER_MIN,
                    "used_weight": used_weight,
                    "requested_weight": safe_weight,
                    "next_weight": next_weight,
                },
            )

class BinanceFuturesAccountIn(BaseModel):
    api_key: str
    api_secret: str


@app.post("/binance/futures-account")
def binance_futures_account(payload: BinanceFuturesAccountIn, x_internal_token: str = Header(default="")):
    _authorize_internal_request(x_internal_token)

    params = {
        "timestamp": int(time.time() * 1000),
    }
    query = urlencode(params)
    signature = hmac.new(
        payload.api_secret.encode("utf-8"),
        query.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    url = f"{BINANCE_FUTURES_BASE}/fapi/v2/account?{query}&signature={signature}"
    headers = {"X-MBX-APIKEY": payload.api_key}

    response = _request_upstream("GET", url, headers=headers, timeout=max(3, REQUEST_TIMEOUT_SECONDS))
    if response.status_code >= 400:
        _raise_upstream_http_error(response)

    data = response.json()
    if not isinstance(data, dict):
        raise HTTPException(status_code=502, detail="invalid_futures_account_payload")

    return {
        "mode": "gateway_futures_account",
        "assets": data.get("assets", []),
        "positions": data.get("positions", []),
    }

