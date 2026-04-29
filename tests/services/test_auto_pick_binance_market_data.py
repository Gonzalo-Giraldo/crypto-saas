from __future__ import annotations

from apps.api.app.services.auto_pick.binance.market_data import (
    fetch_ticker_24h_rows,
    fetch_klines,
    fetch_1h_klines,
    fetch_15m_klines,
)


def test_market_data_returns_empty_without_gateway_env(monkeypatch):
    monkeypatch.delenv("BINANCE_GATEWAY_BASE_URL", raising=False)
    monkeypatch.delenv("BINANCE_GATEWAY_TOKEN", raising=False)

    assert fetch_ticker_24h_rows() == []
    assert fetch_klines("BTCUSDT", "1h", 120) == []
    assert fetch_1h_klines("BTCUSDT") == []
    assert fetch_15m_klines("BTCUSDT") == []
