from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from apps.api.app.services.auto_pick_financial_model import (
    calculate_support_resistance_by_percentiles,
    validate_range,
)


_REQUIRED_OHLC_FIELDS = ("open", "high", "low", "close")


def _decimal(value: Any, field_name: str) -> Decimal:
    try:
        out = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"{field_name}_invalid") from None
    if not out.is_finite():
        raise ValueError(f"{field_name}_not_finite")
    return out


def _normalize_ohlc_candle(raw: dict[str, Any]) -> dict[str, Decimal]:
    """Normalize one OHLC candle and fail closed on incomplete or invalid values."""
    if not isinstance(raw, dict):
        raise ValueError("ohlc_candle_must_be_dict")

    missing = [field for field in _REQUIRED_OHLC_FIELDS if field not in raw]
    if missing:
        raise ValueError(f"ohlc_missing_{'_'.join(missing)}")

    candle = {
        "open": _decimal(raw["open"], "open"),
        "high": _decimal(raw["high"], "high"),
        "low": _decimal(raw["low"], "low"),
        "close": _decimal(raw["close"], "close"),
    }

    if any(value <= 0 for value in candle.values()):
        raise ValueError("ohlc_values_must_be_positive")
    if candle["high"] < candle["low"]:
        raise ValueError("ohlc_high_below_low")
    if candle["open"] > candle["high"] or candle["open"] < candle["low"]:
        raise ValueError("ohlc_open_out_of_range")
    if candle["close"] > candle["high"] or candle["close"] < candle["low"]:
        raise ValueError("ohlc_close_out_of_range")

    return candle


def normalize_ohlc_series(candles: list[dict[str, Any]]) -> list[dict[str, Decimal]]:
    """Normalize an OHLC series without side effects."""
    if not isinstance(candles, list):
        raise ValueError("ohlc_series_must_be_list")
    if not candles:
        raise ValueError("ohlc_series_required")
    return [_normalize_ohlc_candle(candle) for candle in candles]


def extract_ohlc_series(candles: list[dict[str, Any]]) -> dict[str, list[Decimal]]:
    """Extract highs, lows and closes from validated OHLC candles."""
    normalized = normalize_ohlc_series(candles)
    return {
        "highs": [candle["high"] for candle in normalized],
        "lows": [candle["low"] for candle in normalized],
        "closes": [candle["close"] for candle in normalized],
    }


def calculate_market_structure(
    candles: list[dict[str, Any]],
    *,
    support_percentile: Any = "0.1",
    resistance_percentile: Any = "0.9",
    min_range_pct: Any = "0.002",
    max_range_pct: Any = "0.25",
) -> dict[str, Any]:
    """Calculate market structure from already provided OHLC candles."""
    series = extract_ohlc_series(candles)

    support_result = calculate_support_resistance_by_percentiles(
        series["lows"],
        support_percentile=support_percentile,
        resistance_percentile=support_percentile,
    )
    resistance_result = calculate_support_resistance_by_percentiles(
        series["highs"],
        support_percentile=resistance_percentile,
        resistance_percentile=resistance_percentile,
    )

    support = support_result["support"]
    resistance = resistance_result["resistance"]
    current_price = series["closes"][-1]

    range_result = validate_range(
        support=support,
        resistance=resistance,
        current_price=current_price,
        min_range_pct=min_range_pct,
        max_range_pct=max_range_pct,
    )

    return {
        "valid": bool(range_result["valid"]),
        "reason": str(range_result["reason"]),
        "support": support,
        "resistance": resistance,
        "current_price": current_price,
        "range_width": range_result["range_width"],
        "range_pct": range_result["range_pct"],
        "position_in_range": range_result["position_in_range"],
        "candles_count": len(candles),
    }
