from __future__ import annotations

import apps.api.app.services.auto_pick.binance.orchestrator as orch
from apps.api.app.services.auto_pick.contracts import AutoPickDecision, AutoPickNoTrade


def _valid_ticker_rows() -> list[dict]:
    return [
        {
            "symbol": "BTCUSDT",
            "lastPrice": "65000",
            "quoteVolume": "500000000",
            "bidPrice": "64990",
            "askPrice": "65010",
        }
    ]


def _valid_klines(symbol: str) -> list[list]:
    rows = []
    price = 65000.0
    for _ in range(30):
        rows.append([0, price, price * 1.01, price * 0.99, price, 1000])
        price *= 1.001
    return rows


def test_sell_side_from_model_maps_to_short_direction(monkeypatch):
    def fake_model(candidate):
        return {
            "symbol": "BTCUSDT",
            "valid": True,
            "final_score": 1,
            "combined_trend": -0.5,
            "side": "SELL",
        }

    monkeypatch.setattr(orch, "fetch_ticker_24h_rows", _valid_ticker_rows)
    monkeypatch.setattr(orch, "fetch_1h_klines", _valid_klines)
    monkeypatch.setattr(orch, "fetch_15m_klines", _valid_klines)
    monkeypatch.setattr(orch, "compute_final_score", fake_model)

    result = orch.run_binance_auto_pick()

    assert isinstance(result, AutoPickDecision)
    assert result.side == "SELL"
    assert result.direction == "SHORT"


def test_invalid_side_from_model_fails_closed(monkeypatch):
    def fake_model(candidate):
        return {
            "symbol": "BTCUSDT",
            "valid": True,
            "final_score": 1,
            "combined_trend": 0.5,
            "side": "INVALID",
        }

    monkeypatch.setattr(orch, "fetch_ticker_24h_rows", _valid_ticker_rows)
    monkeypatch.setattr(orch, "fetch_1h_klines", _valid_klines)
    monkeypatch.setattr(orch, "fetch_15m_klines", _valid_klines)
    monkeypatch.setattr(orch, "compute_final_score", fake_model)

    result = orch.run_binance_auto_pick()

    assert isinstance(result, AutoPickNoTrade)
    assert result.reason == "no_valid_candidates"
