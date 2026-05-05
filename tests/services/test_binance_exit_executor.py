from __future__ import annotations

from dataclasses import dataclass

from apps.worker.app.engine.binance_exit_executor import create_exit_orders


@dataclass(frozen=True)
class FakeBracketOrders:
    stop_loss_order: dict
    take_profit_order: dict


def _bracket() -> FakeBracketOrders:
    return FakeBracketOrders(
        stop_loss_order={
            "symbol": "BTCUSDT",
            "market": "FUTURES",
            "side": "SELL",
            "type": "STOP_MARKET",
            "quantity": "0.01",
            "stopPrice": "90000",
            "reduceOnly": True,
            "clientAlgoId": "intent-1-SL",
        },
        take_profit_order={
            "symbol": "BTCUSDT",
            "market": "FUTURES",
            "side": "SELL",
            "type": "TAKE_PROFIT_MARKET",
            "quantity": "0.01",
            "stopPrice": "120000",
            "reduceOnly": True,
            "clientAlgoId": "intent-1-TP",
        },
    )


def test_create_exit_orders_sends_sl_and_tp_when_both_ok():
    calls = []
    bracket = _bracket()

    def fake_send_order(payload):
        calls.append(payload)
        if payload["type"] == "STOP_MARKET":
            return {"data": {"algoId": 111}}
        return {"data": {"algoId": 222}}

    result = create_exit_orders(
        bracket_orders=bracket,
        send_order=fake_send_order,
    )

    assert calls == [bracket.stop_loss_order, bracket.take_profit_order]
    assert result == {
        "sl": {
            "clientAlgoId": "intent-1-SL",
            "algoId": 111,
        },
        "tp": {
            "clientAlgoId": "intent-1-TP",
            "algoId": 222,
        },
    }


def test_create_exit_orders_aborts_tp_when_sl_fails():
    calls = []
    bracket = _bracket()

    def fake_send_order(payload):
        calls.append(payload)
        return {"status": "ERROR", "error": "sl_failed"}

    result = create_exit_orders(
        bracket_orders=bracket,
        send_order=fake_send_order,
    )

    assert calls == [bracket.stop_loss_order]
    assert result == {
        "sl": None,
        "tp": None,
        "error": "stop_loss_failed",
    }


def test_create_exit_orders_reports_tp_failure_after_sl_ok():
    calls = []
    bracket = _bracket()

    def fake_send_order(payload):
        calls.append(payload)
        if payload["type"] == "STOP_MARKET":
            return {"data": {"algoId": 111}}
        return {"status": "TIMEOUT", "error": "tp_timeout"}

    result = create_exit_orders(
        bracket_orders=bracket,
        send_order=fake_send_order,
    )

    assert calls == [bracket.stop_loss_order, bracket.take_profit_order]
    assert result == {
        "sl": {
            "clientAlgoId": "intent-1-SL",
            "algoId": 111,
        },
        "tp": None,
        "error": "take_profit_failed",
    }


def test_create_exit_orders_does_not_require_algo_id_when_ok():
    bracket = _bracket()

    result = create_exit_orders(
        bracket_orders=bracket,
        send_order=lambda payload: {"ok": True},
    )

    assert result["sl"]["clientAlgoId"] == "intent-1-SL"
    assert result["sl"]["algoId"] is None
    assert result["tp"]["clientAlgoId"] == "intent-1-TP"
    assert result["tp"]["algoId"] is None


def test_create_exit_orders_accepts_new_client_order_id_fallback():
    bracket = FakeBracketOrders(
        stop_loss_order={
            "type": "STOP_MARKET",
            "newClientOrderId": "intent-1-SL",
        },
        take_profit_order={
            "type": "TAKE_PROFIT_MARKET",
            "newClientOrderId": "intent-1-TP",
        },
    )

    result = create_exit_orders(
        bracket_orders=bracket,
        send_order=lambda payload: {"algoId": 333},
    )

    assert result["sl"]["clientAlgoId"] == "intent-1-SL"
    assert result["sl"]["algoId"] == 333
    assert result["tp"]["clientAlgoId"] == "intent-1-TP"
    assert result["tp"]["algoId"] == 333


def test_create_exit_orders_rejects_missing_orders():
    class Empty:
        pass

    try:
        create_exit_orders(
            bracket_orders=Empty(),
            send_order=lambda payload: {"ok": True},
        )
    except ValueError as exc:
        assert str(exc) == "stop_loss_order_required"
    else:
        raise AssertionError("expected ValueError")
