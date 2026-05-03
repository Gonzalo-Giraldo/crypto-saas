from apps.binance_ws.controlled_user_data_listener import process_user_data_messages


class FakeDB:
    def __init__(self, existing_ids=None):
        self._existing = set(existing_ids or [])

    def execute(self, query, params):
        rows = []
        for v in params.values():
            if v in self._existing:
                rows.append((v,))
        return rows


TRADE = {
    "event": {
        "e": "executionReport",
        "x": "TRADE",
        "X": "FILLED",
        "i": 1,
        "t": 100,
        "l": "1",
        "L": "10",
    }
}

NEW = {
    "event": {
        "e": "executionReport",
        "x": "NEW",
        "t": -1,
    }
}

OTHER = {"event": {"e": "outboundAccountPosition"}}


def test_empty():
    res = process_user_data_messages(
        db=FakeDB(),
        messages=[],
        user_id="u",
        account_id="a",
        persist_binance_fills_db_callable=lambda **k: None,
    )
    assert res["received"] == 0


def test_ignore_non_execution_report():
    res = process_user_data_messages(
        db=FakeDB(),
        messages=[OTHER],
        user_id="u",
        account_id="a",
        persist_binance_fills_db_callable=lambda **k: None,
    )
    assert res["ignored"] == 1


def test_new_not_persisted():
    res = process_user_data_messages(
        db=FakeDB(),
        messages=[NEW],
        user_id="u",
        account_id="a",
        persist_binance_fills_db_callable=lambda **k: None,
    )
    assert res["not_a_fill"] == 1


def test_trade_persisted():
    calls = {}

    def fake(**k):
        calls["called"] = True

    res = process_user_data_messages(
        db=FakeDB(),
        messages=[TRADE],
        user_id="u",
        account_id="a",
        persist_binance_fills_db_callable=fake,
    )

    assert res["processed"] == 1


def test_max_messages():
    res = process_user_data_messages(
        db=FakeDB(),
        messages=[TRADE, TRADE],
        user_id="u",
        account_id="a",
        persist_binance_fills_db_callable=lambda **k: None,
        max_messages=1,
    )
    assert res["received"] == 1


def test_error_handling():
    def bad(**k):
        raise Exception("fail")

    res = process_user_data_messages(
        db=FakeDB(),
        messages=[TRADE],
        user_id="u",
        account_id="a",
        persist_binance_fills_db_callable=bad,
    )
    assert len(res["errors"]) == 1
