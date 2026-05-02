import pytest
from fastapi.testclient import TestClient
from apps.api.app.main import app
from apps.api.app.api.deps import get_current_user, get_db


def override_user():
    class U:
        id = "test-user"
    return U()


class DummyDB:
    def execute(self, *args, **kwargs):
        class Row:
            def __init__(self):
                self._mapping = {
                    "user_id": "test-user",
                    "account_id": "default",
                    "broker": "BINANCE",
                    "market": "SPOT",
                    "symbol": "BTCUSDT",
                    "side": "BUY",
                    "qty": "0.0001",
                    "quote_qty": "7.8",
                    "commission_usdt": "0.01",
                }
        class Result:
            def fetchall(self):
                return [Row()]
        return Result()


def override_db():
    return DummyDB()


app.dependency_overrides[get_current_user] = override_user
app.dependency_overrides[get_db] = override_db

client = TestClient(app)


def test_gateway_timeout_returns_502(monkeypatch):
    from apps.api.app.api import binance_portfolio

    def mock_fetch(*args, **kwargs):
        raise RuntimeError("binance_gateway_timeout")

    monkeypatch.setattr(
        "apps.api.app.api.binance_portfolio.fetch_binance_ticker_price",
        mock_fetch
    )

    response = client.get("/portfolio/binance/unrealized-pnl?symbol=BTCUSDT&account_id=default")

    assert response.status_code == 502
    assert response.json()["detail"] == "binance_gateway_timeout"
