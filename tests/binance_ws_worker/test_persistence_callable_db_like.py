from apps.binance_ws_worker.persistence_callable_db_like import db_like_persistence_callable


def test_insert_single():
    result = db_like_persistence_callable(
        user_id="u",
        account_id="a",
        broker="binance",
        market="spot",
        fills=[{"tradeId": "1", "orderId": "10"}],
    )

    assert result["inserted"] == 1
    assert result["skipped"] == 0
    assert result["inserted_trade_ids"] == ["1"]
    assert result["skipped_trade_ids"] == []


def test_skip_duplicate_same_key():
    result = db_like_persistence_callable(
        user_id="u",
        account_id="a",
        broker="binance",
        market="spot",
        fills=[
            {"tradeId": "1", "orderId": "10"},
            {"tradeId": "1", "orderId": "10"},
        ],
    )

    assert result["inserted"] == 1
    assert result["skipped"] == 1
    assert result["inserted_trade_ids"] == ["1"]
    assert result["skipped_trade_ids"] == ["1"]


def test_requires_user_account():
    try:
        db_like_persistence_callable(
            fills=[{"tradeId": "1", "orderId": "10"}]
        )
    except ValueError:
        pass
    else:
        raise AssertionError



def test_adapter_integration_contract():
    from apps.binance_ws_worker.persistence_adapter import persist_ws_execution_report_message

    result = persist_ws_execution_report_message(
        db=None,
        message={
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
        },
        user_id="u",
        account_id="a",
        persist_callable=db_like_persistence_callable,
    )

    assert result["processed"] is True
    assert result["inserted"] == 1
    assert result["skipped"] == 0
    assert result["trade_id"] == "456"
    assert result["order_id"] == "123"
