from __future__ import annotations

import json
import random
import time
import urllib.error as urllib_error
import urllib.parse as urllib_parse
import urllib.request as urllib_request
from threading import Lock

from apps.api.app.core.config import settings

_binance_ticker_cache_rows: list[dict] = []
_binance_ticker_cache_expiry = 0.0
_binance_ticker_cache_lock = Lock()
_binance_klines_cache: dict = {}
_binance_klines_cache_lock = Lock()


def _fetch_binance_ticker_rows() -> list[dict]:
    cache_ttl = max(0, int(settings.BINANCE_TICKER_CACHE_SECONDS or 0))
    now_ts = time.time()
    if cache_ttl > 0:
        with _binance_ticker_cache_lock:
            if _binance_ticker_cache_rows and now_ts < _binance_ticker_cache_expiry:
                return list(_binance_ticker_cache_rows)

    def _update_cache(rows: list[dict]) -> list[dict]:
        if cache_ttl <= 0:
            return rows
        with _binance_ticker_cache_lock:
            global _binance_ticker_cache_rows, _binance_ticker_cache_expiry
            _binance_ticker_cache_rows = list(rows)
            _binance_ticker_cache_expiry = time.time() + cache_ttl
        return rows

    max_retries = max(0, int(settings.BINANCE_HTTP_MAX_RETRIES or 0))
    backoff_base = max(0.05, float(settings.BINANCE_HTTP_RETRY_BACKOFF_SECONDS or 0.6))

    def _should_retry_http_error(exc: Exception) -> bool:
        if isinstance(exc, urllib_error.HTTPError):
            code = int(getattr(exc, "code", 0) or 0)
            return code == 429 or code >= 500
        return isinstance(exc, urllib_error.URLError)

    def _run_request(req: urllib_request.Request, timeout: int) -> list[dict]:
        attempts = max_retries + 1
        for attempt in range(attempts):
            try:
                with urllib_request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
                    payload = json.loads(resp.read().decode("utf-8"))
                if isinstance(payload, dict):
                    rows = payload.get("rows")
                    if isinstance(rows, list):
                        return [p for p in rows if isinstance(p, dict)]
                if isinstance(payload, list):
                    return [p for p in payload if isinstance(p, dict)]
                return []
            except (urllib_error.URLError, urllib_error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
                is_last = attempt >= attempts - 1
                if is_last or not _should_retry_http_error(exc):
                    break
                sleep_s = backoff_base * (2 ** attempt) + random.uniform(0.0, 0.25)
                time.sleep(sleep_s)
        return []

    gateway_enabled = bool(settings.BINANCE_GATEWAY_ENABLED and settings.BINANCE_GATEWAY_BASE_URL)
    if gateway_enabled:
        base = settings.BINANCE_GATEWAY_BASE_URL.rstrip("/")
        url = f"{base}/binance/ticker-24hr"
        body = json.dumps({"limit": 500}).encode("utf-8")
        req = urllib_request.Request(
            url,
            method="POST",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        if settings.BINANCE_GATEWAY_TOKEN:
            req.add_header("X-Internal-Token", settings.BINANCE_GATEWAY_TOKEN)
        rows = _run_request(req, timeout=max(3, int(settings.BINANCE_GATEWAY_TIMEOUT_SECONDS)))
        if rows:
            return _update_cache(rows)
        if not settings.BINANCE_GATEWAY_FALLBACK_DIRECT:
            with _binance_ticker_cache_lock:
                return list(_binance_ticker_cache_rows)

    base = (settings.BINANCE_SPOT_BASE_URL or settings.BINANCE_TESTNET_BASE_URL or "https://testnet.binance.vision").rstrip("/")
    url = f"{base}/api/v3/ticker/24hr"
    req = urllib_request.Request(url, method="GET")
    rows = _run_request(req, timeout=6)
    if rows:
        return _update_cache(rows)
    with _binance_ticker_cache_lock:
        return list(_binance_ticker_cache_rows)


def _fetch_binance_klines(symbol: str, interval: str, limit: int, start_time_ms: int | None = None, end_time_ms: int | None = None) -> list[list]:
    sym = str(symbol or "").upper().strip()
    iv = str(interval or "1h").strip()
    if not sym:
        return []
    lim = max(30, min(int(limit), 500))
    cache_ttl = max(5, int(settings.BINANCE_MTF_CACHE_SECONDS or 60))
    now_ts = time.time()
    key = (sym, iv, start_time_ms, end_time_ms)
    with _binance_klines_cache_lock:
        cached = _binance_klines_cache.get(key)
        if cached and now_ts < cached[0]:
            return list(cached[1])

    rows: list[list] = []
    gateway_enabled = bool(settings.BINANCE_GATEWAY_ENABLED and settings.BINANCE_GATEWAY_BASE_URL)
    if gateway_enabled:
        try:
            base = settings.BINANCE_GATEWAY_BASE_URL.rstrip("/")
            url = f"{base}/binance/klines"
            gateway_payload = {"symbol": sym, "interval": iv, "limit": lim}
            if start_time_ms is not None:
                gateway_payload["start_time_ms"] = int(start_time_ms)
            if end_time_ms is not None:
                gateway_payload["end_time_ms"] = int(end_time_ms)
            body = json.dumps(gateway_payload).encode("utf-8")
            req = urllib_request.Request(
                url,
                method="POST",
                data=body,
                headers={"Content-Type": "application/json"},
            )
            if settings.BINANCE_GATEWAY_TOKEN:
                req.add_header("X-Internal-Token", settings.BINANCE_GATEWAY_TOKEN)
            with urllib_request.urlopen(req, timeout=max(3, int(settings.BINANCE_GATEWAY_TIMEOUT_SECONDS))) as resp:  # noqa: S310
                payload = json.loads(resp.read().decode("utf-8"))
            got = payload.get("rows") if isinstance(payload, dict) else None
            if isinstance(got, list):
                rows = [row for row in got if isinstance(row, list) and len(row) >= 6]
        except (urllib_error.URLError, urllib_error.HTTPError, TimeoutError, json.JSONDecodeError):
            if not settings.BINANCE_GATEWAY_FALLBACK_DIRECT:
                return []

    if not rows:
        base = (settings.BINANCE_SPOT_BASE_URL or settings.BINANCE_TESTNET_BASE_URL or "https://testnet.binance.vision").rstrip("/")
        params = {"symbol": sym, "interval": iv, "limit": lim}
        if start_time_ms is not None:
            params["startTime"] = int(start_time_ms)
        if end_time_ms is not None:
            params["endTime"] = int(end_time_ms)
        url = f"{base}/api/v3/klines?{urllib_parse.urlencode(params)}"
        try:
            req = urllib_request.Request(url, method="GET")
            with urllib_request.urlopen(req, timeout=6) as resp:  # noqa: S310
                payload = json.loads(resp.read().decode("utf-8"))
        except (urllib_error.URLError, urllib_error.HTTPError, TimeoutError, json.JSONDecodeError):
            return []
        if not isinstance(payload, list):
            return []
        rows = [row for row in payload if isinstance(row, list) and len(row) >= 6]

    with _binance_klines_cache_lock:
        _binance_klines_cache[key] = (time.time() + cache_ttl, rows)
    return rows


def _fetch_binance_1h_klines(symbol: str, limit: int | None = None) -> list[list]:
    sym = str(symbol or "").upper().strip()
    if not sym:
        return []
    lim = max(30, min(int(limit or settings.BINANCE_MTF_KLINES_LIMIT or 120), 500))
    return _fetch_binance_klines(sym, "1h", lim)


def _fetch_binance_15m_klines(symbol: str, limit: int = 96) -> list[list]:
    sym = str(symbol or "").upper().strip()
    if not sym:
        return []
    lim = max(30, min(int(limit), 500))
    return _fetch_binance_klines(sym, "15m", lim)


def _clip(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(value)))


def _norm_return(ret: float, scale: float) -> float:
    if scale <= 0:
        return 0.0
    return _clip(ret / scale, -1.0, 1.0)


def _compute_binance_mtf_signal(symbol: str) -> dict | None:
    rows = _fetch_binance_1h_klines(symbol=symbol)
    if len(rows) < 30:
        return None
    closes: list[float] = []
    highs: list[float] = []
    lows: list[float] = []
    for row in rows:
        try:
            highs.append(float(row[2]))
            lows.append(float(row[3]))
            closes.append(float(row[4]))
        except (TypeError, ValueError):
            return None
    if len(closes) < 30 or closes[-1] <= 0:
        return None

    close_now = closes[-1]
    r_1h = (close_now - closes[-2]) / closes[-2] if closes[-2] > 0 else 0.0
    r_4h = (close_now - closes[-5]) / closes[-5] if closes[-5] > 0 else 0.0
    r_1d = (close_now - closes[-25]) / closes[-25] if closes[-25] > 0 else 0.0
    r_6h = (close_now - closes[-7]) / closes[-7] if closes[-7] > 0 else 0.0

    trend_score = (
        0.55 * _norm_return(r_1d, 0.03)
        + 0.30 * _norm_return(r_4h, 0.02)
        + 0.15 * _norm_return(r_1h, 0.01)
    )
    momentum_score = (
        0.60 * _norm_return(r_1h, 0.01)
        + 0.40 * _norm_return(r_6h, 0.015)
    )

    start_idx = max(1, len(closes) - 24)
    trs: list[float] = []
    for i in range(start_idx, len(closes)):
        prev_close = closes[i - 1]
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - prev_close),
            abs(lows[i] - prev_close),
        )
        trs.append(max(0.0, tr))
    atr = sum(trs) / len(trs) if trs else 0.0
    atr_pct = (atr / close_now) * 100.0 if close_now > 0 else 0.0

    micro_15m = None
    rows_15m = _fetch_binance_15m_klines(symbol=symbol, limit=96)
    if len(rows_15m) >= 7:
        closes_15m: list[float] = []
        for row in rows_15m:
            try:
                closes_15m.append(float(row[4]))
            except (TypeError, ValueError):
                closes_15m = []
                break
        if len(closes_15m) >= 7 and closes_15m[-1] > 0:
            c_now = closes_15m[-1]
            r15_1 = (c_now - closes_15m[-2]) / closes_15m[-2] if closes_15m[-2] > 0 else 0.0
            r15_3 = (c_now - closes_15m[-4]) / closes_15m[-4] if closes_15m[-4] > 0 else 0.0
            r15_6 = (c_now - closes_15m[-7]) / closes_15m[-7] if closes_15m[-7] > 0 else 0.0
            micro_raw = (0.5 * r15_6) + (0.3 * r15_3) + (0.2 * r15_1)
            micro_15m = round(_clip(micro_raw / 0.012, -1.0, 1.0), 4)

    return {
        "trend_score": round(_clip(trend_score, -1.0, 1.0), 4),
        "momentum_score": round(_clip(momentum_score, -1.0, 1.0), 4),
        "atr_pct": round(max(0.0, atr_pct), 4),
        "trend_1d": round(r_1d, 6),
        "trend_4h": round(r_4h, 6),
        "trend_1h": round(r_1h, 6),
        "micro_trend_15m": micro_15m,
        "source": "klines_1h_mtf",
    }
