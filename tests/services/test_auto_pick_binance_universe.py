from __future__ import annotations

from apps.api.app.services.auto_pick.binance.universe import build_candidate_symbols


def test_build_candidate_symbols_filters_invalid_rows_and_deduplicates():
    rows = [
        {"symbol": "BTCUSDT", "lastPrice": "65000", "quoteVolume": "2000000"},
        {"symbol": "ETHUSDT", "lastPrice": "3000", "quoteVolume": "999999"},
        {"symbol": "BNBBTC", "lastPrice": "0.01", "quoteVolume": "5000000"},
        {"symbol": "SOLUSDT", "lastPrice": "0", "quoteVolume": "5000000"},
        {"symbol": "ADAUSDT", "lastPrice": "1.2", "quoteVolume": "1500000"},
        {"symbol": "BTCUSDT", "lastPrice": "65000", "quoteVolume": "2000000"},
        {"symbol": "", "lastPrice": "1", "quoteVolume": "2000000"},
        {"symbol": "XRPUSDT", "lastPrice": "bad", "quoteVolume": "2000000"},
        {"not_symbol": "NOPE", "lastPrice": "1", "quoteVolume": "2000000"},
    ]

    assert build_candidate_symbols(rows, min_quote_volume=1_000_000) == ["BTCUSDT", "ADAUSDT"]


def test_build_candidate_symbols_fail_closed_for_bad_threshold():
    assert build_candidate_symbols([], min_quote_volume=1_000_000) == []
    assert build_candidate_symbols([{"symbol": "DOGEUSDT", "lastPrice": "1", "quoteVolume": "100"}], min_quote_volume=1_000_000) == []
    assert build_candidate_symbols([{"symbol": "DOGEUSDT", "lastPrice": "1", "quoteVolume": "100"}], min_quote_volume=-1) == []
