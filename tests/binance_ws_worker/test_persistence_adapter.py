from apps.binance_ws_worker.persistence_adapter import persist_ws_execution_report_message


def _trade_msg():
    return {
        "event": {
            "e": "executionReport",
            "x": "TRADE",
            "t": 100,
            "i": 200,
            "s": "BTCUSDT",
            "S": "BUY",
            "l": "0.01",
            "L": "50000",
            "n": "0.001",
            "N": "BNB",
            "T": 123456789,
        }
    }


def test_not_a_fill():
    msg = {"event": {"e": "executionReport", "x": "NEW"}}

    called = {"n": 0}

    def fake(**kwargs):
        called["n"] += 1

    result = persist_ws_execution_report_message(
        db=None,
        message=msg,
        user_id="u",
        account_id="a",
        persist_callable=fake,
    )

    assert result["processed"] is False
    assert result["reason"] == "not_a_fill"
    assert called["n"] == 0


def test_trade_calls_persist():
    msg = _trade_msg()

    captured = {}

    def fake(**kwargs):
        captured.update(kwargs)
        return {"inserted": 1, "skipped": 0}

    result = persist_ws_execution_report_message(
        db="db",
        message=msg,
        user_id="user",
        account_id="acc",
        persist_callable=fake,
    )

    assert result["processed"] is True
    assert captured["db"] == "db"
    assert captured["user_id"] == "user"
    assert captured["account_id"] == "acc"
    assert captured["broker"] == "BINANCE"
    assert captured["market"] == "SPOT"
    assert captured["fills"][0]["tradeId"] == "100"

    assert result["inserted"] == 1
    assert result["skipped"] == 0


def test_persist_none_result():
    msg = _trade_msg()

    def fake(**kwargs):
        return None

    result = persist_ws_execution_report_message(
        db=None,
        message=msg,
        user_id="u",
        account_id="a",
        persist_callable=fake,
    )

    assert result["inserted"] == 0
    assert result["skipped"] == 0


def test_called_once():
    msg = _trade_msg()

    count = {"n": 0}

    def fake(**kwargs):
        count["n"] += 1
        return {"inserted": 1, "skipped": 0}

    persist_ws_execution_report_message(
        db=None,
        message=msg,
        user_id="u",
        account_id="a",
        persist_callable=fake,
    )

    assert count["n"] == 1
