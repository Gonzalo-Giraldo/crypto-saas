from apps.binance_ws.manual_persist_execution_report_batch import (
    persist_manual_execution_report_payloads,
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


NEW_EVENT = {
    "subscriptionId": 0,
    "event": {
        "e": "executionReport",
        "x": "NEW",
        "X": "NEW",
        "i": 61330568137,
        "t": -1,
    },
}


def test_empty_list():
    db = FakeDB()

    result = persist_manual_execution_report_payloads(
        db=db,
        payloads=[],
        user_id="u",
        account_id="a",
        persist_binance_fills_db_callable=lambda **kwargs: None,
    )

    assert result["received"] == 0
    assert result["processed"] == 0
    assert result["not_a_fill"] == 0
    assert result["results"] == []
    assert db.execute_count == 0


def test_new_plus_trade_filled():
    calls = []

    def fake_persist(**kwargs):
        calls.append(kwargs)

    result = persist_manual_execution_report_payloads(
        db=FakeDB(),
        payloads=[NEW_EVENT, REAL_TRADE_EVENT],
        user_id="u",
        account_id="a",
        persist_binance_fills_db_callable=fake_persist,
    )

    assert result["received"] == 2
    assert result["not_a_fill"] == 1
    assert result["processed"] == 1
    assert result["inserted_candidate_count"] == 1
    assert result["inserted_trade_ids"] == ["6268132893"]
    assert len(calls) == 1


def test_trade_partially_filled():
    calls = []

    def fake_persist(**kwargs):
        calls.append(kwargs)

    partial = {
        "subscriptionId": 0,
        "event": {
            **REAL_TRADE_EVENT["event"],
            "X": "PARTIALLY_FILLED",
            "t": 6268132894,
            "l": "0.00003000",
            "z": "0.00008000",
        },
    }

    result = persist_manual_execution_report_payloads(
        db=FakeDB(),
        payloads=[partial],
        user_id="u",
        account_id="a",
        persist_binance_fills_db_callable=fake_persist,
    )

    assert result["processed"] == 1
    assert result["inserted_trade_ids"] == ["6268132894"]
    assert calls[0]["fills"][0]["qty"] == "0.00003000"


def test_duplicate_inside_batch_delegates_once_in_summary():
    calls = []

    def fake_persist(**kwargs):
        calls.append(kwargs)

    result = persist_manual_execution_report_payloads(
        db=FakeDB(),
        payloads=[REAL_TRADE_EVENT, REAL_TRADE_EVENT],
        user_id="u",
        account_id="a",
        persist_binance_fills_db_callable=fake_persist,
    )

    assert result["received"] == 2
    assert result["processed"] == 2
    assert result["inserted_candidate_count"] == 1
    assert result["skipped_duplicate_in_batch_count"] == 1
    assert result["inserted_trade_ids"] == ["6268132893"]


def test_existing_in_fake_db_is_skipped():
    calls = []

    def fake_persist(**kwargs):
        calls.append(kwargs)

    result = persist_manual_execution_report_payloads(
        db=FakeDB(existing_ids={"6268132893"}),
        payloads=[REAL_TRADE_EVENT],
        user_id="u",
        account_id="a",
        persist_binance_fills_db_callable=fake_persist,
    )

    assert result["processed"] == 1
    assert result["inserted_candidate_count"] == 0
    assert result["skipped_existing_count"] == 1
    assert result["skipped_trade_ids"] == ["6268132893"]
    assert calls == []


def test_accumulates_inserted_and_skipped_trade_ids():
    calls = []

    def fake_persist(**kwargs):
        calls.append(kwargs)

    second = {
        "subscriptionId": 0,
        "event": {
            **REAL_TRADE_EVENT["event"],
            "t": 6268132895,
        },
    }

    result = persist_manual_execution_report_payloads(
        db=FakeDB(existing_ids={"6268132893"}),
        payloads=[REAL_TRADE_EVENT, second],
        user_id="u",
        account_id="a",
        persist_binance_fills_db_callable=fake_persist,
    )

    assert result["inserted_trade_ids"] == ["6268132895"]
    assert result["skipped_trade_ids"] == ["6268132893"]
    assert result["inserted_candidate_count"] == 1
    assert result["skipped_existing_count"] == 1


def test_module_has_no_forbidden_runtime_dependencies():
    import apps.binance_ws.manual_persist_execution_report_batch as target

    assert hasattr(target, "persist_manual_execution_report_payloads")
