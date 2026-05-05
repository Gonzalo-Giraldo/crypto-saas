from apps.worker.app.engine.binance_exit_plan import build_binance_exit_plan


def _fill_basis(**overrides):
    base = {
        "filled_qty": "0.01",
        "avg_entry_price": "100",
        "usable_for_exits": True,
        "reason": "ok",
    }
    base.update(overrides)
    return base


def _risk_inputs(**overrides):
    base = {
        "available": True,
        "stop_loss": "90",
        "take_profit": "120",
        "expected_qty": "999",
    }
    base.update(overrides)
    return base


def test_builds_long_exit_plan_from_real_fill_basis():
    result = build_binance_exit_plan(
        symbol="btcusdt",
        side="BUY",
        fill_basis=_fill_basis(filled_qty="0.02", avg_entry_price="100"),
        risk_inputs=_risk_inputs(stop_loss="90", take_profit="120"),
        client_order_id="intent-1",
    )

    assert result == {
        "available": True,
        "reason": "ok",
        "symbol": "BTCUSDT",
        "direction": "LONG",
        "filled_qty": "0.02",
        "avg_entry_price": "100",
        "stop_loss": "90",
        "take_profit": "120",
        "client_order_id": "intent-1",
    }


def test_builds_short_exit_plan_from_sell_side():
    result = build_binance_exit_plan(
        symbol="ETHUSDT",
        side="SELL",
        fill_basis=_fill_basis(filled_qty="0.5", avg_entry_price="100"),
        risk_inputs=_risk_inputs(stop_loss="110", take_profit="80"),
        client_order_id="intent-2",
    )

    assert result["available"] is True
    assert result["direction"] == "SHORT"
    assert result["filled_qty"] == "0.5"
    assert result["avg_entry_price"] == "100"


def test_rejects_unusable_fill_basis():
    result = build_binance_exit_plan(
        symbol="BTCUSDT",
        side="BUY",
        fill_basis=_fill_basis(usable_for_exits=False),
        risk_inputs=_risk_inputs(),
        client_order_id="intent-1",
    )

    assert result == {"available": False, "reason": "fill_basis_not_usable"}


def test_rejects_missing_risk_inputs():
    result = build_binance_exit_plan(
        symbol="BTCUSDT",
        side="BUY",
        fill_basis=_fill_basis(),
        risk_inputs={"available": False},
        client_order_id="intent-1",
    )

    assert result == {"available": False, "reason": "risk_inputs_not_available"}


def test_uses_filled_qty_not_expected_qty():
    result = build_binance_exit_plan(
        symbol="BTCUSDT",
        side="BUY",
        fill_basis=_fill_basis(filled_qty="0.123"),
        risk_inputs=_risk_inputs(expected_qty="999"),
        client_order_id="intent-1",
    )

    assert result["available"] is True
    assert result["filled_qty"] == "0.123"
    assert "expected_qty" not in result


def test_rejects_invalid_side():
    result = build_binance_exit_plan(
        symbol="BTCUSDT",
        side="HOLD",
        fill_basis=_fill_basis(),
        risk_inputs=_risk_inputs(),
        client_order_id="intent-1",
    )

    assert result == {"available": False, "reason": "invalid_side"}


def test_rejects_invalid_numeric_inputs():
    cases = [
        ("filled_qty", _fill_basis(filled_qty="0"), _risk_inputs(), "filled_qty_invalid"),
        ("avg_entry_price", _fill_basis(avg_entry_price="0"), _risk_inputs(), "avg_entry_price_invalid"),
        ("stop_loss", _fill_basis(), _risk_inputs(stop_loss="0"), "stop_loss_invalid"),
        ("take_profit", _fill_basis(), _risk_inputs(take_profit="invalid"), "take_profit_invalid"),
    ]

    for _, fill_basis, risk_inputs, reason in cases:
        result = build_binance_exit_plan(
            symbol="BTCUSDT",
            side="BUY",
            fill_basis=fill_basis,
            risk_inputs=risk_inputs,
            client_order_id="intent-1",
        )
        assert result == {"available": False, "reason": reason}
