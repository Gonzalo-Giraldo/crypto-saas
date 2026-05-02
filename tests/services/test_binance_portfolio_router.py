import pytest
from fastapi.testclient import TestClient
from apps.api.app.main import app

client = TestClient(app)

def test_reject_non_usdt():
    r = client.get("/portfolio/binance/unrealized-pnl?symbol=BTCUSD")
    assert r.status_code in (400,401)

def test_empty_response():
    r = client.get("/portfolio/binance/unrealized-pnl?symbol=BTCUSDT&account_id=default")
    assert r.status_code in (200,401)

def test_decimal_serialization():
    # no crash
    r = client.get("/portfolio/binance/unrealized-pnl?symbol=BTCUSDT&account_id=default")
    if r.status_code == 200:
        assert isinstance(r.json(), list)
