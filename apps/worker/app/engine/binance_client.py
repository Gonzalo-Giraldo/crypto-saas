import hashlib
import hmac
import time
import threading
import re
from decimal import Decimal, InvalidOperation, ROUND_DOWN
from urllib.parse import urlencode

import requests

from apps.api.app.core.config import settings


_exchange_info_cache_lock = threading.Lock()
_exchange_info_by_symbol: dict[str, dict] = {}
_exchange_info_cache_expiry: float = 0.0
_price_cache_lock = threading.Lock()
_price_by_symbol: dict[str, float] = {}
_price_cache_expiry: float = 0.0


def _normalize_market(market: str | None) -> str:
    m = str(market or "SPOT").upper().strip()
    return "FUTURES" if m == "FUTURES" else "SPOT"


def _base_url_for_market(market: str) -> str:
    if market == "FUTURES":
        return settings.BINANCE_FUTURES_BASE_URL.rstrip("/")
    return settings.BINANCE_TESTNET_BASE_URL.rstrip("/")


def _order_test_endpoint_for_market(market: str) -> str:
    return "/fapi/v1/order/test" if market == "FUTURES" else "/api/v3/order/test"


def _exchange_info_endpoint_for_market(market: str) -> str:
    return "/fapi/v1/exchangeInfo" if market == "FUTURES" else "/api/v3/exchangeInfo"


def _ticker_price_endpoint_for_market(market: str) -> str:
    return "/fapi/v1/ticker/price" if market == "FUTURES" else "/api/v3/ticker/price"


def _gateway_enabled() -> bool:
    return bool(settings.BINANCE_GATEWAY_ENABLED and settings.BINANCE_GATEWAY_BASE_URL)


def _gateway_headers() -> dict[str, str]:
    out = {"Content-Type": "application/json"}
    if settings.BINANCE_GATEWAY_TOKEN:
        out["X-Internal-Token"] = settings.BINANCE_GATEWAY_TOKEN
    return out


def _extract_upstream_code(text: str) -> str | None:
    msg = str(text or "")
    m = re.search(r"\bcode=([A-Za-z0-9_\-]+)", msg)
    if m:
        return m.group(1)
    m = re.search(r'"code"\s*:\s*"?([A-Za-z0-9_\-]+)"?', msg)
    if m:
        return m.group(1)
    return None


def _build_gateway_error(status_code: int, body_text: str) -> str:
    detail = f"gateway_upstream_error status={int(status_code)}"
    code = _extract_upstream_code(body_text)
    if code:
        detail += f" code={code}"
    return detail


def _post_gateway(path: str, payload: dict, timeout: int = 10) -> dict | None:
    if not _gateway_enabled():
        return None
    base = settings.BINANCE_GATEWAY_BASE_URL.rstrip("/")
    url = f"{base}{path}"
    response = requests.post(
        url,
        headers=_gateway_headers(),
        json=payload,
        timeout=max(3, timeout),
    )
    if response.status_code >= 400:
        raise RuntimeError(_build_gateway_error(response.status_code, response.text))
    body = response.json()
    return body if isinstance(body, dict) else None


def send_test_order(
    api_key: str,
    api_secret: str,
    symbol: str,
    side: str,
    quantity: float,
    order_type: str = "MARKET",
    client_order_id: str | None = None,
    market: str = "SPOT",
):
    market_norm = _normalize_market(market)
    endpoint = _order_test_endpoint_for_market(market_norm)
    base_url = _base_url_for_market(market_norm)

    params = {
        "symbol": symbol.upper(),
        "side": side.upper(),
        "type": order_type.upper(),
        "quantity": quantity,
        "timestamp": int(time.time() * 1000),
    }
    if client_order_id:
        params["newClientOrderId"] = client_order_id[:36]

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


def _fetch_exchange_info_rows_with_gateway_fallback(
    *,
    wanted: list[str],
    market: str,
    direct_url: str,
) -> list | None:
    rows = None
    if _gateway_enabled():
        try:
            body = _post_gateway(
                "/binance/exchange-info",
                {"symbols": wanted, "market": market},
                timeout=max(3, int(settings.BINANCE_GATEWAY_TIMEOUT_SECONDS)),
            )
            got = body.get("symbols") if isinstance(body, dict) else None
            if isinstance(got, list):
                rows = got
        except Exception:
            if not settings.BINANCE_GATEWAY_FALLBACK_DIRECT:
                raise
    if rows is None:
        response = requests.get(direct_url, timeout=10)
        if response.status_code >= 400:
            detail = response.text
            raise RuntimeError(f"Binance exchangeInfo error {response.status_code}: {detail}")
        body = response.json()
        rows = body.get("symbols") if isinstance(body, dict) else None
    return rows if isinstance(rows, list) else None


def _fetch_exchange_info_symbols(symbols: list[str]) -> dict[str, dict]:
    global _exchange_info_by_symbol, _exchange_info_cache_expiry
    wanted = sorted({str(s or "").upper().strip() for s in symbols if str(s or "").strip()})
    if not wanted:
        return {}
    now = time.time()
    ttl = max(30, int(settings.BINANCE_EXCHANGE_INFO_CACHE_SECONDS or 600))
    with _exchange_info_cache_lock:
        if _exchange_info_by_symbol and now < _exchange_info_cache_expiry:
            return {s: _exchange_info_by_symbol[s] for s in wanted if s in _exchange_info_by_symbol}

    endpoint = _exchange_info_endpoint_for_market("SPOT")
    base_url = _base_url_for_market("SPOT")
    query = urlencode({"symbols": str(wanted).replace("'", '"')})
    url = f"{base_url}{endpoint}?{query}"
    rows = _fetch_exchange_info_rows_with_gateway_fallback(
        wanted=wanted,
        market="SPOT",
        direct_url=url,
    )
    if not isinstance(rows, list):
        return {}
    parsed: dict[str, dict] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        symbol = str(row.get("symbol") or "").upper().strip()
        if not symbol:
            continue
        parsed[symbol] = row
    with _exchange_info_cache_lock:
        _exchange_info_by_symbol = dict(parsed)
        _exchange_info_cache_expiry = time.time() + ttl
    return {s: parsed[s] for s in wanted if s in parsed}


def _fetch_symbol_price(symbol: str) -> float | None:
    global _price_cache_expiry
    sym = str(symbol or "").upper().strip()
    if not sym:
        return None
    now = time.time()
    ttl = max(2, int(settings.BINANCE_PRICE_CACHE_SECONDS or 15))
    with _price_cache_lock:
        if _price_by_symbol and now < _price_cache_expiry and sym in _price_by_symbol:
            return float(_price_by_symbol[sym])

    body = None
    if _gateway_enabled():
        try:
            got = _post_gateway(
                "/binance/ticker-price",
                {"symbol": sym, "market": "SPOT"},
                timeout=max(3, int(settings.BINANCE_GATEWAY_TIMEOUT_SECONDS)),
            )
            row = got.get("row") if isinstance(got, dict) else None
            if isinstance(row, dict):
                body = row
        except Exception:
            if not settings.BINANCE_GATEWAY_FALLBACK_DIRECT:
                return None
    if body is None:
        endpoint = _ticker_price_endpoint_for_market("SPOT")
        base_url = _base_url_for_market("SPOT")
        query = urlencode({"symbol": sym})
        url = f"{base_url}{endpoint}?{query}"
        response = requests.get(url, timeout=8)
        if response.status_code >= 400:
            return None
        body = response.json()
    try:
        px = float(body.get("price") or 0.0)
    except Exception:
        return None
    if px <= 0:
        return None
    with _price_cache_lock:
        _price_by_symbol[sym] = px
        _price_cache_expiry = time.time() + ttl
    return px


def _to_decimal(value: str | float | int | None, default: str = "0") -> Decimal:
    try:
        return Decimal(str(value if value is not None else default))
    except (InvalidOperation, ValueError):
        return Decimal(default)


def _normalize_qty_to_step(qty: Decimal, step: Decimal) -> Decimal:
    if step <= 0:
        return qty
    units = (qty / step).to_integral_value(rounding=ROUND_DOWN)
    return units * step


def prepare_binance_market_order_quantity(
    symbol: str,
    requested_qty: float,
    market: str = "SPOT",
) -> dict:
    market_norm = _normalize_market(market)
    sym = str(symbol or "").upper().strip()
    if not sym:
        raise RuntimeError("symbol is required")
    req_qty = _to_decimal(requested_qty, "0")
    if req_qty <= 0:
        raise RuntimeError("quantity must be > 0")

    if market_norm == "FUTURES":
        info = _fetch_exchange_info_symbols_for_market([sym], market="FUTURES").get(sym)
    else:
        info = _fetch_exchange_info_symbols([sym]).get(sym)
    if not info:
        raise RuntimeError(f"Binance exchangeInfo missing for {sym}")

    status_raw = info.get("status")
    if status_raw is None:
        status_raw = info.get("contractStatus")
    if status_raw is not None:
        status = str(status_raw).upper().strip()
        if status and status != "TRADING":
            raise RuntimeError(f"symbol_not_trading status={status} symbol={sym} market={market_norm}")

    order_types_raw = info.get("orderTypes")
    if order_types_raw is None:
        order_types_raw = info.get("orderType")
    order_types: set[str] = set()
    if isinstance(order_types_raw, (list, tuple, set)):
        order_types = {str(x).upper().strip() for x in order_types_raw if str(x).strip()}
    elif isinstance(order_types_raw, str):
        order_types = {s.strip().upper() for s in order_types_raw.split(",") if s.strip()}
    if order_types and "MARKET" not in order_types:
        raise RuntimeError(f"market_order_not_allowed orderTypes={sorted(order_types)} symbol={sym} market={market_norm}")

    filters = {str(f.get("filterType") or ""): f for f in info.get("filters") or [] if isinstance(f, dict)}
    lot = filters.get("MARKET_LOT_SIZE") or filters.get("LOT_SIZE") or {}
    min_qty = _to_decimal(lot.get("minQty"), "0")
    max_qty = _to_decimal(lot.get("maxQty"), "0")
    step = _to_decimal(lot.get("stepSize"), "0")
    qty_norm = _normalize_qty_to_step(req_qty, step) if step > 0 else req_qty
    if min_qty > 0 and qty_norm < min_qty:
        raise RuntimeError(
            f"qty_below_min_qty requested={req_qty} normalized={qty_norm} minQty={min_qty} symbol={sym}"
        )
    if max_qty > 0 and qty_norm > max_qty:
        raise RuntimeError(
            f"qty_above_max_qty requested={req_qty} normalized={qty_norm} maxQty={max_qty} symbol={sym}"
        )
    if qty_norm <= 0:
        raise RuntimeError(f"qty_normalized_to_zero requested={req_qty} stepSize={step} symbol={sym}")

    min_notional = Decimal("0")
    notional_filter = filters.get("NOTIONAL")
    if isinstance(notional_filter, dict):
        min_notional = _to_decimal(notional_filter.get("minNotional"), "0")
    if min_notional <= 0:
        mn = filters.get("MIN_NOTIONAL")
        if isinstance(mn, dict):
            min_notional = _to_decimal(mn.get("minNotional"), "0")
    if market_norm == "FUTURES":
        price = _to_decimal(_fetch_symbol_price_for_market(sym, market="FUTURES"), "0")
    else:
        price = _to_decimal(_fetch_symbol_price(sym), "0")
    if min_notional > 0 and price <= 0:
        raise RuntimeError(f"notional_price_unavailable minNotional={min_notional} symbol={sym} market={market_norm}")
    notional = qty_norm * price if price > 0 else Decimal("0")
    if min_notional > 0 and price > 0 and notional < min_notional:
        raise RuntimeError(
            f"notional_below_min notional={notional} minNotional={min_notional} price={price} qty={qty_norm} symbol={sym}"
        )

    return {
        "symbol": sym,
        "requested_qty": float(req_qty),
        "normalized_qty": float(qty_norm),
        "step_size": float(step),
        "min_qty": float(min_qty),
        "max_qty": float(max_qty),
        "min_notional": float(min_notional),
        "price": float(price) if price > 0 else None,
        "estimated_notional": float(notional) if notional > 0 else None,
        "market": market_norm,
    }


def get_account_status(
    api_key: str,
    api_secret: str,
):
    endpoint = "/api/v3/account"
    base_url = settings.BINANCE_TESTNET_BASE_URL.rstrip("/")
    params = {
        "timestamp": int(time.time() * 1000),
    }
    query = urlencode(params)
    signature = hmac.new(
        api_secret.encode("utf-8"),
        query.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    url = f"{base_url}{endpoint}?{query}&signature={signature}"
    headers = {"X-MBX-APIKEY": api_key}

    response = requests.get(url, headers=headers, timeout=10)
    if response.status_code >= 400:
        detail = response.text
        raise RuntimeError(f"Binance account error {response.status_code}: {detail}")
    return response.json()


def _fetch_exchange_info_symbols_for_market(symbols: list[str], market: str = "SPOT") -> dict[str, dict]:
    market_norm = _normalize_market(market)
    if market_norm == "SPOT":
        return _fetch_exchange_info_symbols(symbols)
    wanted = sorted({str(s or "").upper().strip() for s in symbols if str(s or "").strip()})
    if not wanted:
        return {}
    endpoint = _exchange_info_endpoint_for_market(market_norm)
    base_url = _base_url_for_market(market_norm)
    url = f"{base_url}{endpoint}"
    if market_norm == "FUTURES" and len(wanted) == 1:
        url = f"{url}?{urlencode({'symbol': wanted[0]})}"
    rows = _fetch_exchange_info_rows_with_gateway_fallback(
        wanted=wanted,
        market=market_norm,
        direct_url=url,
    )
    if not isinstance(rows, list):
        return {}
    parsed: dict[str, dict] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        symbol = str(row.get("symbol") or "").upper().strip()
        if symbol in wanted:
            parsed[symbol] = row
    return parsed


def _fetch_symbol_price_for_market(symbol: str, market: str = "SPOT") -> float | None:
    market_norm = _normalize_market(market)
    if market_norm == "SPOT":
        return _fetch_symbol_price(symbol)
    sym = str(symbol or "").upper().strip()
    if not sym:
        return None
    body = None
    if _gateway_enabled():
        try:
            got = _post_gateway(
                "/binance/ticker-price",
                {"symbol": sym, "market": market_norm},
                timeout=max(3, int(settings.BINANCE_GATEWAY_TIMEOUT_SECONDS)),
            )
            row = got.get("row") if isinstance(got, dict) else None
            if isinstance(row, dict):
                body = row
        except Exception:
            if not settings.BINANCE_GATEWAY_FALLBACK_DIRECT:
                return None
    if body is None:
        endpoint = _ticker_price_endpoint_for_market(market_norm)
        base_url = _base_url_for_market(market_norm)
        query = urlencode({"symbol": sym})
        response = requests.get(f"{base_url}{endpoint}?{query}", timeout=8)
        if response.status_code >= 400:
            return None
        body = response.json()
    try:
        px = float(body.get("price") or 0.0)
    except Exception:
        return None
    return px if px > 0 else None
