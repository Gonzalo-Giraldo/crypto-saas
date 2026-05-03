from apps.binance_ws.controlled_ws_batch_runner import run_controlled_ws_batch


class FakeDB:
    def execute(self, query, params):
        return []


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


def test_empty_batch():
    res = run_controlled_ws_batch(
        db=FakeDB(),
        messages=[],
        user_id="u",
        account_id="a",
        persist_binance_fills_db_callable=lambda **k: None,
    )
    assert res["received"] == 0


def test_limit_messages():
    res = run_controlled_ws_batch(
        db=FakeDB(),
        messages=[TRADE, TRADE],
        user_id="u",
        account_id="a",
        persist_binance_fills_db_callable=lambda **k: None,
        max_messages=1,
    )
    assert res["received"] == 1
