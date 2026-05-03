from apps.binance_ws_worker.persistence_callable_safe import safe_noop_persistence_callable


def test_safe_callable_valid_fill():
    result = safe_noop_persistence_callable(
        fills=[{
            "tradeId": "1",
            "orderId": "2",
            "qty": "0.1",
            "price": "100"
        }]
    )
    assert result["inserted"] == 0
    assert result["skipped"] == 1


def test_safe_callable_requires_trade_id():
    try:
        safe_noop_persistence_callable(fills=[{"orderId": "1"}])
    except ValueError:
        pass
    else:
        raise AssertionError


def test_safe_callable_requires_order_id():
    try:
        safe_noop_persistence_callable(fills=[{"tradeId": "1"}])
    except ValueError:
        pass
    else:
        raise AssertionError


def test_runtime_adapter_safe_noop_integration():
    from apps.binance_ws_worker.persistence_adapter import persist_ws_execution_report_message

    message = {
        "event": {
            "e": "executionReport",
            "x": "TRADE",
            "t": 456,
            "i": 123,
            "s": "BTCUSDT",
            "S": "BUY",
            "l": "0.01",
            "L": "50000",
        }
    }

    result = persist_ws_execution_report_message(
        db=None,
        message=message,
        user_id="",
        account_id="",
        persist_callable=safe_noop_persistence_callable,
    )

    assert result["processed"] is True
    assert result["reason"] == "fill"
    assert result["inserted"] == 0
    assert result["skipped"] == 1
    assert result["trade_id"] == "456"
    assert result["order_id"] == "123"
