from apps.binance_ws.execution_report_parser import parse_execution_report_event


REAL_TRADE_FILLED_EVENT = {
    "subscriptionId": 0,
    "event": {
        "e": "executionReport",
        "E": 1777771535839,
        "s": "BTCUSDT",
        "c": "web_17f4ee6098884acbb6f9153338e38b4a",
        "S": "BUY",
        "o": "MARKET",
        "x": "TRADE",
        "X": "FILLED",
        "i": 61330568137,
        "l": "0.00008000",
        "z": "0.00008000",
        "L": "78272.37000000",
        "n": "0.00000762",
        "N": "BNB",
        "T": 1777771535839,
        "t": 6268132893,
        "Z": "6.26178960",
        "Y": "6.26178960",
    },
}


def test_payload_not_dict_returns_none():
    assert parse_execution_report_event(None) is None
    assert parse_execution_report_event("not-a-dict") is None


def test_payload_without_event_returns_none():
    assert parse_execution_report_event({"subscriptionId": 0}) is None


def test_non_execution_report_returns_none():
    payload = {
        "subscriptionId": 0,
        "event": {
            "e": "balanceUpdate",
            "a": "BTC",
            "d": "0.0001",
        },
    }

    assert parse_execution_report_event(payload) is None


def test_execution_report_new_returns_none():
    payload = {
        "subscriptionId": 0,
        "event": {
            "e": "executionReport",
            "x": "NEW",
            "X": "NEW",
            "i": 61330568137,
            "t": -1,
        },
    }

    assert parse_execution_report_event(payload) is None


def test_execution_report_trade_filled_real_event_returns_candidate_fill():
    parsed = parse_execution_report_event(REAL_TRADE_FILLED_EVENT)

    assert parsed == {
        "broker": "BINANCE",
        "market": "SPOT",
        "symbol": "BTCUSDT",
        "side": "BUY",
        "order_id": "61330568137",
        "trade_id": "6268132893",
        "qty": "0.00008000",
        "price": "78272.37000000",
        "quote_qty": "6.26178960",
        "commission": "0.00000762",
        "commission_asset": "BNB",
        "executed_at_ms": 1777771535839,
        "raw_event": REAL_TRADE_FILLED_EVENT["event"],
    }


def test_execution_report_trade_partially_filled_returns_candidate_fill():
    payload = {
        "subscriptionId": 0,
        "event": {
            **REAL_TRADE_FILLED_EVENT["event"],
            "x": "TRADE",
            "X": "PARTIALLY_FILLED",
            "t": 6268132894,
            "l": "0.00003000",
            "z": "0.00008000",
        },
    }

    parsed = parse_execution_report_event(payload)

    assert parsed is not None
    assert parsed["broker"] == "BINANCE"
    assert parsed["market"] == "SPOT"
    assert parsed["symbol"] == "BTCUSDT"
    assert parsed["side"] == "BUY"
    assert parsed["order_id"] == "61330568137"
    assert parsed["trade_id"] == "6268132894"
    assert parsed["qty"] == "0.00003000"
    assert parsed["qty"] != "0.00008000"
    assert parsed["price"] == "78272.37000000"
    assert parsed["quote_qty"] == "6.26178960"
    assert parsed["commission"] == "0.00000762"
    assert parsed["commission_asset"] == "BNB"
    assert parsed["executed_at_ms"] == 1777771535839
    assert parsed["raw_event"] == payload["event"]




def test_trade_id_minus_one_returns_none():
    payload = {
        "subscriptionId": 0,
        "event": {
            **REAL_TRADE_FILLED_EVENT["event"],
            "t": -1,
        },
    }

    assert parse_execution_report_event(payload) is None


def test_outbound_account_position_returns_none():
    payload = {
        "subscriptionId": 0,
        "event": {
            "e": "outboundAccountPosition",
            "E": 1777771535839,
            "u": 1777771535839,
            "B": [
                {
                    "a": "BTC",
                    "f": "0.00008000",
                    "l": "0.00000000",
                }
            ],
        },
    }

    assert parse_execution_report_event(payload) is None
