from decimal import Decimal

import pytest

from apps.api.app.services.auto_pick_market_structure import (
    calculate_market_structure,
    extract_ohlc_series,
    normalize_ohlc_series,
)


def test_normalize_ohlc_series_accepts_valid_candles():
    candles = [
        {"open": "100", "high": "110", "low": "90", "close": "105"},
        {"open": "105", "high": "112", "low": "101", "close": "108"},
    ]

    out = normalize_ohlc_series(candles)

    assert out[0]["open"] == Decimal("100")
    assert out[1]["close"] == Decimal("108")


def test_normalize_ohlc_series_rejects_empty_series():
    with pytest.raises(ValueError, match="ohlc_series_required"):
        normalize_ohlc_series([])


def test_normalize_ohlc_series_rejects_missing_field():
    with pytest.raises(ValueError, match="ohlc_missing_close"):
        normalize_ohlc_series([{"open": "100", "high": "110", "low": "90"}])


def test_normalize_ohlc_series_rejects_high_below_low():
    with pytest.raises(ValueError, match="ohlc_high_below_low"):
        normalize_ohlc_series([{"open": "100", "high": "90", "low": "110", "close": "100"}])


def test_normalize_ohlc_series_rejects_open_out_of_range():
    with pytest.raises(ValueError, match="ohlc_open_out_of_range"):
        normalize_ohlc_series([{"open": "120", "high": "110", "low": "90", "close": "100"}])


def test_normalize_ohlc_series_rejects_close_out_of_range():
    with pytest.raises(ValueError, match="ohlc_close_out_of_range"):
        normalize_ohlc_series([{"open": "100", "high": "110", "low": "90", "close": "120"}])


def test_extract_ohlc_series_returns_highs_lows_closes():
    candles = [
        {"open": "100", "high": "110", "low": "90", "close": "105"},
        {"open": "105", "high": "112", "low": "101", "close": "108"},
    ]

    out = extract_ohlc_series(candles)

    assert out["highs"] == [Decimal("110"), Decimal("112")]
    assert out["lows"] == [Decimal("90"), Decimal("101")]
    assert out["closes"] == [Decimal("105"), Decimal("108")]


def test_calculate_market_structure_returns_complete_structure():
    candles = [
        {"open": "100", "high": "110", "low": "90", "close": "105"},
        {"open": "105", "high": "112", "low": "101", "close": "108"},
        {"open": "108", "high": "116", "low": "104", "close": "114"},
    ]

    out = calculate_market_structure(candles)

    assert set(out.keys()) == {
        "valid",
        "reason",
        "support",
        "resistance",
        "current_price",
        "range_width",
        "range_pct",
        "position_in_range",
        "candles_count",
    }
    assert out["candles_count"] == 3
    assert out["support"] > 0
    assert out["resistance"] > out["support"]
    assert Decimal("0") <= out["position_in_range"] <= Decimal("1")


def test_calculate_market_structure_fail_closed_for_flat_invalid_range():
    candles = [
        {"open": "100", "high": "100", "low": "100", "close": "100"},
        {"open": "100", "high": "100", "low": "100", "close": "100"},
    ]

    out = calculate_market_structure(candles)

    assert out["valid"] is False
    assert out["reason"] in {"invalid_range", "range_pct_out_of_bounds"}


def test_calculate_market_structure_uses_lows_for_support_highs_for_resistance_and_close_for_current_price():
    candles = [
        {"open": "100", "high": "150", "low": "90", "close": "149"},
        {"open": "110", "high": "160", "low": "80", "close": "159"},
        {"open": "120", "high": "170", "low": "70", "close": "169"},
    ]

    out = calculate_market_structure(candles)

    assert out["support"] == Decimal("72")
    assert out["resistance"] == Decimal("168")
    assert out["current_price"] == Decimal("169")
