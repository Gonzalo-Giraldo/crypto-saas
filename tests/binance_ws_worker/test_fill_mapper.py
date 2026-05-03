from apps.binance_ws_worker.fill_mapper import map_execution_report_to_binance_fill


def test_ignore_non_dict():
    assert map_execution_report_to_binance_fill(None) is None


def test_ignore_non_event():
    assert map_execution_report_to_binance_fill({}) is None


def test_ignore_wrong_event_type():
    msg = {"event": {"e": "outboundAccountPosition"}}
    assert map_execution_report_to_binance_fill(msg) is None


def test_ignore_non_trade():
    msg = {"event": {"e": "executionReport", "x": "NEW"}}
    assert map_execution_report_to_binance_fill(msg) is None


def test_ignore_trade_id_minus_one():
    msg = {"event": {"e": "executionReport", "x": "TRADE", "t": -1, "i": 1}}
    assert map_execution_report_to_binance_fill(msg) is None


def test_ignore_missing_order_id():
    msg = {"event": {"e": "executionReport", "x": "TRADE", "t": 1}}
    assert map_execution_report_to_binance_fill(msg) is None


def test_valid_trade_filled():
    msg = {
        "event": {
            "e": "executionReport",
            "x": "TRADE",
            "X": "FILLED",
            "t": 100,
            "i": 200,
            "s": "BTCUSDT",
            "S": "BUY",
            "l": "0.01",
            "L": "50000",
            "Z": "500",
            "n": "0.001",
            "N": "BNB",
            "T": 123456789,
        }
    }

    result = map_execution_report_to_binance_fill(msg)

    assert result["tradeId"] == "100"
    assert result["orderId"] == "200"
    assert result["qty"] == "0.01"
    assert result["price"] == "50000"
    assert result["quoteQty"] == "500.00"


def test_partial_fill():
    msg = {
        "event": {
            "e": "executionReport",
            "x": "TRADE",
            "X": "PARTIALLY_FILLED",
            "t": 101,
            "i": 201,
            "s": "BTCUSDT",
            "S": "SELL",
            "l": "0.02",
            "L": "40000",
            "n": "0.002",
            "N": "USDT",
            "T": 987654321,
        }
    }

    result = map_execution_report_to_binance_fill(msg)

    assert result["tradeId"] == "101"
    assert result["quoteQty"] == "800.00"


def test_qty_uses_l_not_z():
    msg = {
        "event": {
            "e": "executionReport",
            "x": "TRADE",
            "t": 102,
            "i": 202,
            "s": "BTCUSDT",
            "S": "BUY",
            "l": "0.01",
            "z": "0.5",
            "L": "10000",
        }
    }

    result = map_execution_report_to_binance_fill(msg)
    assert result["qty"] == "0.01"


def test_quote_qty_calculated_not_Z():
    msg = {
        "event": {
            "e": "executionReport",
            "x": "TRADE",
            "t": 103,
            "i": 203,
            "s": "BTCUSDT",
            "S": "BUY",
            "l": "0.01",
            "L": "10000",
            "Z": "9999",
        }
    }

    result = map_execution_report_to_binance_fill(msg)
    assert result["quoteQty"] == "100.00"
