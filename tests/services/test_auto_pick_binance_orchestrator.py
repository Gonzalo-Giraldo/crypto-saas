from __future__ import annotations

from apps.api.app.services.auto_pick.binance import orchestrator as orch
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
        rows.append([
            0,
            price,
            price * 1.01,
            price * 0.99,
            price,
            1000,
        ])
        price *= 1.001
    return rows


def test_run_binance_auto_pick_fail_closed_without_ticker_data(monkeypatch):
    monkeypatch.setattr(orch, "fetch_ticker_24h_rows", lambda: [])

    result = orch.run_binance_auto_pick()

    assert isinstance(result, AutoPickNoTrade)
    assert result.broker == "BINANCE"
    assert result.reason == "no_ticker_data"


def test_run_binance_auto_pick_positive_path_with_monkeypatched_data(monkeypatch):
    monkeypatch.setattr(orch, "fetch_ticker_24h_rows", _valid_ticker_rows)
    monkeypatch.setattr(orch, "fetch_1h_klines", _valid_klines)
    monkeypatch.setattr(orch, "fetch_15m_klines", _valid_klines)

    result = orch.run_binance_auto_pick()

    assert isinstance(result, AutoPickDecision)
    assert result.symbol == "BTCUSDT"
    assert result.side == "BUY"
    assert result.direction == "LONG"
    assert result.broker == "BINANCE"
    assert result.asset_profile == "CRYPTO"
    assert result.model_version == "binance_auto_pick_pipeline_v1"
    assert result.final_score > 0


def test_run_binance_auto_pick_fail_closed_when_no_valid_candidates(monkeypatch):
    monkeypatch.setattr(orch, "fetch_ticker_24h_rows", _valid_ticker_rows)
    monkeypatch.setattr(orch, "fetch_1h_klines", lambda symbol: [])
    monkeypatch.setattr(orch, "fetch_15m_klines", lambda symbol: [])

    result = orch.run_binance_auto_pick()

    assert isinstance(result, AutoPickNoTrade)
    assert result.broker == "BINANCE"
    assert result.reason == "no_valid_candidates"
