from apps.binance_ws.manual_persist_execution_report import (
    persist_manual_execution_report_payload,
)


class FakeDB:
    def __init__(self, existing_ids=None):
        self._existing = set(existing_ids or [])
        self.last_query = None
        self.last_params = None
        self.execute_count = 0

    def execute(self, query, params):
        self.execute_count += 1
        self.last_query = str(query)
        self.last_params = params
        rows = []
        for value in params.values():
            if value in self._existing:
                rows.append((value,))
        return rows


REAL_TRADE_EVENT = {
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


def test_new_returns_not_a_fill_and_does_not_persist():
    calls = {}

    def fake_persist(**kwargs):
        calls["called"] = True

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

    db = FakeDB()

    result = persist_manual_execution_report_payload(
        db=db,
        payload=payload,
        user_id="u",
        account_id="a",
        persist_binance_fills_db_callable=fake_persist,
    )

    assert result == {
        "processed": False,
        "reason": "not_a_fill",
    }
    assert calls == {}
    assert db.execute_count == 0


def test_trade_filled_calls_wrapper_and_persistence():
    calls = {}

    def fake_persist(**kwargs):
        calls.update(kwargs)

    db = FakeDB()

    result = persist_manual_execution_report_payload(
        db=db,
        payload=REAL_TRADE_EVENT,
        user_id="u",
        account_id="a",
        persist_binance_fills_db_callable=fake_persist,
    )

    assert result["processed"] is True
    assert result["reason"] == "fill_candidate"
    assert result["result"]["inserted_candidate_count"] == 1
    assert calls["broker"] == "BINANCE"
    assert calls["market"] == "SPOT"
    assert calls["fills"][0]["tradeId"] == "6268132893"
    assert calls["fills"][0]["orderId"] == "61330568137"


def test_trade_partially_filled_calls_wrapper_and_persistence():
    calls = {}

    def fake_persist(**kwargs):
        calls.update(kwargs)

    payload = {
        "subscriptionId": 0,
        "event": {
            **REAL_TRADE_EVENT["event"],
            "X": "PARTIALLY_FILLED",
            "t": 6268132894,
            "l": "0.00003000",
            "z": "0.00008000",
        },
    }

    result = persist_manual_execution_report_payload(
        db=FakeDB(),
        payload=payload,
        user_id="u",
        account_id="a",
        persist_binance_fills_db_callable=fake_persist,
    )

    assert result["processed"] is True
    assert result["result"]["inserted_trade_ids"] == ["6268132894"]
    assert calls["fills"][0]["tradeId"] == "6268132894"
    assert calls["fills"][0]["qty"] == "0.00003000"


def test_returns_wrapper_result_for_existing_fill():
    calls = {}

    def fake_persist(**kwargs):
        calls["called"] = True

    result = persist_manual_execution_report_payload(
        db=FakeDB(existing_ids={"6268132893"}),
        payload=REAL_TRADE_EVENT,
        user_id="u",
        account_id="a",
        persist_binance_fills_db_callable=fake_persist,
    )

    assert result["processed"] is True
    assert result["reason"] == "fill_candidate"
    assert result["result"]["inserted_candidate_count"] == 0
    assert result["result"]["skipped_existing_count"] == 1
    assert calls == {}


def test_module_has_no_runtime_side_effect_dependencies():
    import apps.binance_ws.manual_persist_execution_report as target

    assert hasattr(target, "persist_manual_execution_report_payload")
