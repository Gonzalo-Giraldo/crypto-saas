import pytest

from apps.api.app.services.binance_trades_gateway_client import fetch_binance_trades


def test_client_rejects_missing_api_key(monkeypatch):
    monkeypatch.setattr("apps.api.app.services.binance_trades_gateway_client.settings.BINANCE_GATEWAY_ENABLED", True)
    monkeypatch.setattr("apps.api.app.services.binance_trades_gateway_client.settings.BINANCE_GATEWAY_BASE_URL", "https://gateway.example")

    with pytest.raises(ValueError, match="api_key_required"):
        fetch_binance_trades(api_key="", api_secret="s", symbol="BTCUSDT", market="SPOT")


def test_client_rejects_invalid_market(monkeypatch):
    monkeypatch.setattr("apps.api.app.services.binance_trades_gateway_client.settings.BINANCE_GATEWAY_ENABLED", True)
    monkeypatch.setattr("apps.api.app.services.binance_trades_gateway_client.settings.BINANCE_GATEWAY_BASE_URL", "https://gateway.example")

    with pytest.raises(ValueError, match="market_must_be_SPOT_or_FUTURES"):
        fetch_binance_trades(api_key="k", api_secret="s", symbol="BTCUSDT", market="BTCUSDT")


def test_client_requires_gateway_enabled(monkeypatch):
    monkeypatch.setattr("apps.api.app.services.binance_trades_gateway_client.settings.BINANCE_GATEWAY_ENABLED", False)
    monkeypatch.setattr("apps.api.app.services.binance_trades_gateway_client.settings.BINANCE_GATEWAY_BASE_URL", "https://gateway.example")

    with pytest.raises(RuntimeError, match="binance_gateway_not_configured"):
        fetch_binance_trades(api_key="k", api_secret="s", symbol="BTCUSDT", market="SPOT")
