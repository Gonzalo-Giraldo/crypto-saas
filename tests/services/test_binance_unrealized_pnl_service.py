from decimal import Decimal
import pytest
from apps.api.app.services.binance_unrealized_pnl_service import compute_binance_unrealized_pnl


def test_real_case():
    fills = [{
        "user_id": "u1",
        "account_id": "a1",
        "broker": "BINANCE",
        "market": "SPOT",
        "symbol": "BTCUSDT",
        "side": "BUY",
        "qty": "0.00010000",
        "quote_qty": "7.83000100",
        "commission_usdt": "0.0058677163",
    }]

    r = compute_binance_unrealized_pnl(fills, Decimal("78427.32"))[0]

    assert r["gross_unrealized_pnl_usdt"] == Decimal("0.012731000000")
    assert r["net_unrealized_pnl_usdt"] == Decimal("0.0068632837000000")


def test_partial_sell():
    fills = [
        {"user_id":"u","account_id":"a","broker":"BINANCE","market":"SPOT","symbol":"BTC","side":"BUY","qty":"1","quote_qty":"100","commission_usdt":"1"},
        {"user_id":"u","account_id":"a","broker":"BINANCE","market":"SPOT","symbol":"BTC","side":"SELL","qty":"0.4","quote_qty":"48","commission_usdt":"0.5"},
    ]

    r = compute_binance_unrealized_pnl(fills, Decimal("130"))[0]

    assert r["net_qty"] == Decimal("0.6")
    assert r["gross_unrealized_pnl_usdt"] == Decimal("26")
    assert r["net_unrealized_pnl_usdt"] == Decimal("24.5")


def test_closed():
    fills = [
        {"user_id":"u","account_id":"a","broker":"BINANCE","market":"SPOT","symbol":"BTC","side":"BUY","qty":"1","quote_qty":"100","commission_usdt":"1"},
        {"user_id":"u","account_id":"a","broker":"BINANCE","market":"SPOT","symbol":"BTC","side":"SELL","qty":"1","quote_qty":"120","commission_usdt":"1"},
    ]

    r = compute_binance_unrealized_pnl(fills, Decimal("130"))[0]

    assert r["status"] == "CLOSED"
    assert r["gross_unrealized_pnl_usdt"] == Decimal("20")
    assert r["net_unrealized_pnl_usdt"] == Decimal("18")


def test_invalid_price():
    with pytest.raises(ValueError):
        compute_binance_unrealized_pnl([], Decimal("0"))


def test_invalid_side():
    fills = [{
        "user_id":"u","account_id":"a","broker":"BINANCE","market":"SPOT","symbol":"BTC","side":"X","qty":"1","quote_qty":"1","commission_usdt":"0"
    }]
    with pytest.raises(ValueError):
        compute_binance_unrealized_pnl(fills, Decimal("1"))


def test_net_short_rejected():
    fills = [
        {"user_id":"u","account_id":"a","broker":"BINANCE","market":"SPOT","symbol":"BTC","side":"SELL","qty":"1","quote_qty":"100","commission_usdt":"0"},
    ]
    with pytest.raises(ValueError):
        compute_binance_unrealized_pnl(fills, Decimal("100"))
