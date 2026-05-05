from __future__ import annotations

import pytest

from apps.worker.app.engine.binance_futures_exit_orders import build_binance_futures_bracket_orders


def test_long_futures_bracket_orders():
    out = build_binance_futures_bracket_orders(
        symbol="btcusdt",
        direction="LONG",
        qty="0.01",
        entry_price="100",
        stop_loss="90",
        take_profit="120",
        client_order_id="intent-1",
    )

    assert out.entry_order == {
        "symbol": "BTCUSDT",
        "market": "FUTURES",
        "side": "BUY",
        "type": "MARKET",
        "quantity": "0.01",
        "newClientOrderId": "intent-1",
    }

    assert out.stop_loss_order["side"] == "SELL"
    assert out.stop_loss_order["type"] == "STOP_MARKET"
    assert out.stop_loss_order["stopPrice"] == "90"
    assert out.stop_loss_order["reduceOnly"] is True

    assert out.take_profit_order["side"] == "SELL"
    assert out.take_profit_order["type"] == "TAKE_PROFIT_MARKET"
    assert out.take_profit_order["stopPrice"] == "120"
    assert out.take_profit_order["reduceOnly"] is True


def test_short_futures_bracket_orders():
    out = build_binance_futures_bracket_orders(
        symbol="ETHUSDT",
        direction="SHORT",
        qty="0.5",
        entry_price="100",
        stop_loss="110",
        take_profit="80",
        client_order_id="intent-2",
    )

    assert out.entry_order["side"] == "SELL"
    assert out.entry_order["market"] == "FUTURES"

    assert out.stop_loss_order["side"] == "BUY"
    assert out.stop_loss_order["type"] == "STOP_MARKET"
    assert out.stop_loss_order["stopPrice"] == "110"
    assert out.stop_loss_order["reduceOnly"] is True

    assert out.take_profit_order["side"] == "BUY"
    assert out.take_profit_order["type"] == "TAKE_PROFIT_MARKET"
    assert out.take_profit_order["stopPrice"] == "80"
    assert out.take_profit_order["reduceOnly"] is True


def test_sl_required():
    with pytest.raises(ValueError, match="stop_loss_invalid"):
        build_binance_futures_bracket_orders(
            symbol="BTCUSDT",
            direction="LONG",
            qty="0.01",
            entry_price="100",
            stop_loss=None,
            take_profit="120",
            client_order_id="intent-1",
        )


def test_tp_required():
    with pytest.raises(ValueError, match="take_profit_invalid"):
        build_binance_futures_bracket_orders(
            symbol="BTCUSDT",
            direction="LONG",
            qty="0.01",
            entry_price="100",
            stop_loss="90",
            take_profit=None,
            client_order_id="intent-1",
        )


def test_long_invalid_sl_tp_rejected():
    with pytest.raises(ValueError, match="invalid_SL_TP_for_LONG"):
        build_binance_futures_bracket_orders(
            symbol="BTCUSDT",
            direction="LONG",
            qty="0.01",
            entry_price="100",
            stop_loss="110",
            take_profit="120",
            client_order_id="intent-1",
        )


def test_short_invalid_sl_tp_rejected():
    with pytest.raises(ValueError, match="invalid_SL_TP_for_SHORT"):
        build_binance_futures_bracket_orders(
            symbol="BTCUSDT",
            direction="SHORT",
            qty="0.01",
            entry_price="100",
            stop_loss="90",
            take_profit="80",
            client_order_id="intent-1",
        )


def test_no_db_no_broker_execution_dependencies():
    import apps.worker.app.engine.binance_futures_exit_orders as module

    source = module.__loader__.get_source(module.__name__)

    forbidden = [
        "requests.",
        "SessionLocal",
        "db.commit",
        "send_order",
        "send_order_real",
        "ops.py",
        "api_secret",
        "api_key",
    ]

    for item in forbidden:
        assert item not in source
