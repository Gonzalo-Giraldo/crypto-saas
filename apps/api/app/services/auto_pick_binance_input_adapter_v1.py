from __future__ import annotations

from math import isfinite
from typing import Any

REFERENCE_QUOTE_VOLUME = 200_000_000.0
MAX_SPREAD_BPS = 30.0


def _to_float(value: Any, field_name: str) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name}_invalid") from None
    if not isfinite(out):
        raise ValueError(f"{field_name}_not_finite")
    return out


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    value = _to_float(value, "value")
    return max(low, min(high, value))


def _norm_return(value: float, scale: float) -> float:
    if scale <= 0:
        raise ValueError("scale_invalid")
    return _clamp(value / scale, -1.0, 1.0)


def _parse_klines(rows: list[list], *, field_name: str, min_rows: int) -> dict[str, list[float]]:
    if not isinstance(rows, list) or len(rows) < min_rows:
        raise ValueError(f"{field_name}_insufficient")

    out = {"open": [], "high": [], "low": [], "close": [], "volume": []}

    for idx, row in enumerate(rows):
        if not isinstance(row, list) or len(row) < 6:
            raise ValueError(f"{field_name}_row_{idx}_invalid")

        open_ = _to_float(row[1], f"{field_name}_open")
        high = _to_float(row[2], f"{field_name}_high")
        low = _to_float(row[3], f"{field_name}_low")
        close = _to_float(row[4], f"{field_name}_close")
        volume = _to_float(row[5], f"{field_name}_volume")

        if open_ <= 0 or high <= 0 or low <= 0 or close <= 0 or volume <= 0:
            raise ValueError(f"{field_name}_row_{idx}_non_positive")
        if high < low:
            raise ValueError(f"{field_name}_row_{idx}_high_below_low")
        if not low <= open_ <= high:
            raise ValueError(f"{field_name}_row_{idx}_open_out_of_range")
        if not low <= close <= high:
            raise ValueError(f"{field_name}_row_{idx}_close_out_of_range")

        out["open"].append(open_)
        out["high"].append(high)
        out["low"].append(low)
        out["close"].append(close)
        out["volume"].append(volume)

    return out


def _require_ticker(ticker_24h: dict | None) -> dict:
    if not isinstance(ticker_24h, dict):
        raise ValueError("ticker_24h_required")
    return ticker_24h


def _get_quote_volume(ticker: dict) -> float:
    for key in ("quoteVolume", "quote_volume"):
        if key in ticker:
            val = _to_float(ticker[key], key)
            if val <= 0:
                raise ValueError("quote_volume_non_positive")
            return val
    raise ValueError("quote_volume_required")


def _get_bid_ask(ticker: dict) -> tuple[float, float]:
    bid = ticker.get("bidPrice") or ticker.get("bid_price")
    ask = ticker.get("askPrice") or ticker.get("ask_price")

    if bid is None:
        raise ValueError("bidPrice_required")
    if ask is None:
        raise ValueError("askPrice_required")

    bid_f = _to_float(bid, "bidPrice")
    ask_f = _to_float(ask, "askPrice")

    if bid_f <= 0 or ask_f <= 0:
        raise ValueError("bid_ask_non_positive")
    if ask_f < bid_f:
        raise ValueError("ask_below_bid")

    return bid_f, ask_f


def _spread_bps(bid: float, ask: float) -> float:
    mid = (bid + ask) / 2.0
    return ((ask - bid) / mid) * 10000.0


def _liquidity_state(volume_relative: float, spread_bps: float) -> str:
    if spread_bps > MAX_SPREAD_BPS:
        return "red"
    if volume_relative >= 0.75:
        return "green"
    if volume_relative >= 0.25:
        return "gray"
    return "red"


def _atr_risk(parsed_1h: dict[str, list[float]]) -> float:
    highs = parsed_1h["high"]
    lows = parsed_1h["low"]
    closes = parsed_1h["close"]

    if len(closes) < 24:
        raise ValueError("atr_requires_24_klines")

    trs = []
    start = max(1, len(closes) - 24)
    for i in range(start, len(closes)):
        prev_close = closes[i - 1]
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - prev_close),
            abs(lows[i] - prev_close),
        )
        trs.append(tr)

    atr = sum(trs) / len(trs)
    atr_pct = (atr / closes[-1]) * 100.0

    return _clamp(atr_pct / 8.0, 0.0, 1.0)


def _momentum(closes: list[float]) -> float:
    if len(closes) < 7:
        raise ValueError("momentum_requires_7_closes")

    r1 = (closes[-1] - closes[-2]) / closes[-2]
    r6 = (closes[-1] - closes[-7]) / closes[-7]

    return _clamp(0.60 * _norm_return(r1, 0.01) + 0.40 * _norm_return(r6, 0.015))


def _trend_swing(closes: list[float]) -> float:
    if len(closes) < 25:
        raise ValueError("trend_swing_requires_25_closes")

    r1 = (closes[-1] - closes[-2]) / closes[-2]
    r6 = (closes[-1] - closes[-7]) / closes[-7]
    r24 = (closes[-1] - closes[-25]) / closes[-25]

    return _clamp(
        0.55 * _norm_return(r24, 0.03)
        + 0.30 * _norm_return(r6, 0.015)
        + 0.15 * _norm_return(r1, 0.01),
        -1.0,
        1.0,
    )


def _trend_intraday(klines_15m: list[list] | None) -> float:
    if not klines_15m:
        raise ValueError("klines_15m_required")

    parsed = _parse_klines(klines_15m, field_name="klines_15m", min_rows=7)
    closes = parsed["close"]

    r15 = (closes[-1] - closes[-2]) / closes[-2]
    r45 = (closes[-1] - closes[-4]) / closes[-4]
    r90 = (closes[-1] - closes[-7]) / closes[-7]

    return _clamp(
        0.50 * _norm_return(r90, 0.012)
        + 0.30 * _norm_return(r45, 0.008)
        + 0.20 * _norm_return(r15, 0.004),
        -1.0,
        1.0,
    )


def build_crypto_model_input(*, symbol: str, klines_1h: list[list], klines_15m: list[list] | None = None, ticker_24h: dict | None = None) -> dict:
    symbol_norm = str(symbol or "").upper().strip()
    if not symbol_norm:
        raise ValueError("symbol_required")

    parsed_1h = _parse_klines(klines_1h, field_name="klines_1h", min_rows=25)

    ticker = _require_ticker(ticker_24h)
    quote_volume = _get_quote_volume(ticker)

    bid, ask = _get_bid_ask(ticker)
    spread = _spread_bps(bid, ask)

    volume_relative = _clamp(quote_volume / REFERENCE_QUOTE_VOLUME)

    trend_swing = _trend_swing(parsed_1h["close"])

    return {
        "symbol": symbol_norm,
        "ohlc": parsed_1h,
        "market_metrics": {
            "momentum": _momentum(parsed_1h["close"]),
            "volume_relative": volume_relative,
            "atr_risk": _atr_risk(parsed_1h),
            "liquidity_state": _liquidity_state(volume_relative, spread),
            "trend_swing": trend_swing,
            "trend_intraday": _trend_intraday(klines_15m),
            "spread_bps": spread,
        },
    }
