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
