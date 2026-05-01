from apps.api.app.services.binance_financial_state_service import compute_binance_order_financial_state


def _trade(qty):
    return {
        "qty": qty,
        "orderId": "100",
    }


def test_complete():
    result = compute_binance_order_financial_state(
        execution_ref="100",
        symbol="BTCUSDT",
        market="SPOT",
        fills=[_trade("1.0")],
        expected_qty="1.0",
    )
    assert result["financial_state"] == "COMPLETE"


def test_partial():
    result = compute_binance_order_financial_state(
        execution_ref="100",
        symbol="BTCUSDT",
        market="SPOT",
        fills=[_trade("0.5")],
        expected_qty="1.0",
    )
    assert result["financial_state"] == "INCOMPLETE"


def test_overfilled():
    result = compute_binance_order_financial_state(
        execution_ref="100",
        symbol="BTCUSDT",
        market="SPOT",
        fills=[_trade("1.5")],
        expected_qty="1.0",
    )
    assert result["financial_state"] == "INVALID"
