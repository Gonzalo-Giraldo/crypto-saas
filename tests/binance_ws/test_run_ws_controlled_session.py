import pytest

from apps.binance_ws.run_ws_controlled_session import run_controlled_ws_session


class FakeDB:
    def __init__(self, existing_ids=None):
        self._existing = set(existing_ids or [])
        self.execute_count = 0
        self.last_query = None
        self.last_params = None

    def execute(self, query, params):
        self.execute_count += 1
        self.last_query = str(query)
        self.last_params = params

        results = []
        for v in params.values():
            if v in self._existing:
                results.append((v,))
        return results


class FakeWSClient:
    def __init__(self, messages=None, error_on_calls=None):
        self.messages = list(messages or [])
        self.error_on_calls = set(error_on_calls or [])
        self.calls = 0

    def receive(self):
        self.calls += 1
        if self.calls in self.error_on_calls:
            raise RuntimeError("receive_error")
        if self.calls <= len(self.messages):
            return self.messages[self.calls - 1]
        return {"subscriptionId": 0, "event": {"e": "outboundAccountPosition"}}


def wrapped_event(event):
    return {"subscriptionId": 0, "event": event}


def filled_event(trade_id=1001, order_id=61308219232):
    return wrapped_event(
        {
            "e": "executionReport",
            "x": "TRADE",
            "X": "FILLED",
            "i": order_id,
            "t": trade_id,
            "s": "BTCUSDT",
            "S": "BUY",
            "l": "0.00010000",
            "L": "78300.01000000",
            "Z": "7.83000100",
            "n": "0.00000010",
            "N": "BTC",
            "T": 1710000000000,
        }
    )


def new_event(order_id=61308219233):
    return wrapped_event(
        {
            "e": "executionReport",
            "x": "NEW",
            "X": "NEW",
            "i": order_id,
            "t": -1,
        }
    )


def ignored_event():
    return wrapped_event({"e": "outboundAccountPosition", "u": 1710000000000})


def fake_persist(**kwargs):
    payload = kwargs.get("payload") or {}

    if payload.get("x") == "NEW" and payload.get("X") == "NEW":
        return {"not_a_fill": 1}

    if payload.get("x") == "TRADE" and payload.get("X") in {"FILLED", "PARTIALLY_FILLED"}:
        return {
            "inserted_candidate_count": 1,
            "inserted_trade_ids": [payload.get("t")],
        }

    return {}


def test_max_messages_required_and_positive():
    with pytest.raises(ValueError):
        run_controlled_ws_session(
            ws_client=FakeWSClient(),
            db=FakeDB(),
            user_id="u",
            account_id="a",
            persist_binance_fills_db_callable=fake_persist,
            max_messages=0,
        )

    with pytest.raises(ValueError):
        run_controlled_ws_session(
            ws_client=FakeWSClient(),
            db=FakeDB(),
            user_id="u",
            account_id="a",
            persist_binance_fills_db_callable=fake_persist,
            max_messages=-1,
        )


def test_receive_messages_with_real_event_wrapper():
    ws = FakeWSClient(messages=[ignored_event()])
    summary = run_controlled_ws_session(
        ws_client=ws,
        db=FakeDB(),
        user_id="u",
        account_id="a",
        persist_binance_fills_db_callable=fake_persist,
        max_messages=1,
    )

    assert ws.calls == 1
    assert summary["received"] == 1
    assert summary["ignored"] == 1


def test_cuts_when_max_messages_reached():
    ws = FakeWSClient(messages=[filled_event(1001), filled_event(1002), ignored_event()])
    summary = run_controlled_ws_session(
        ws_client=ws,
        db=FakeDB(),
        user_id="u",
        account_id="a",
        persist_binance_fills_db_callable=fake_persist,
        max_messages=1,
    )

    assert ws.calls == 1
    assert summary["received"] == 1
    assert summary["execution_reports"] == 1
    assert summary["inserted_candidate_count"] == 1
    assert summary["inserted_trade_ids"] == ["1001"]


def test_ignores_non_execution_report_wrapped_event():
    ws = FakeWSClient(messages=[ignored_event()])
    summary = run_controlled_ws_session(
        ws_client=ws,
        db=FakeDB(),
        user_id="u",
        account_id="a",
        persist_binance_fills_db_callable=fake_persist,
        max_messages=1,
    )

    assert summary["received"] == 1
    assert summary["execution_reports"] == 0
    assert summary["ignored"] == 1
    assert summary["processed"] == 0


def test_processes_trade_filled_wrapped_event():
    ws = FakeWSClient(messages=[filled_event(1001)])
    summary = run_controlled_ws_session(
        ws_client=ws,
        db=FakeDB(),
        user_id="u",
        account_id="a",
        persist_binance_fills_db_callable=fake_persist,
        max_messages=1,
    )

    assert summary["received"] == 1
    assert summary["execution_reports"] == 1
    assert summary["processed"] == 1
    assert summary["inserted_candidate_count"] == 1
    assert summary["inserted_trade_ids"] == ["1001"]


def test_processes_new_wrapped_event_as_not_a_fill():
    ws = FakeWSClient(messages=[new_event()])
    summary = run_controlled_ws_session(
        ws_client=ws,
        db=FakeDB(),
        user_id="u",
        account_id="a",
        persist_binance_fills_db_callable=fake_persist,
        max_messages=1,
    )

    assert summary["received"] == 1
    assert summary["execution_reports"] == 1
    assert summary["processed"] == 0
    assert summary["not_a_fill"] == 1
    assert summary["inserted_candidate_count"] == 0


def test_receive_error_is_reported_and_not_hidden():
    ws = FakeWSClient(messages=[filled_event(1001)], error_on_calls={1})
    summary = run_controlled_ws_session(
        ws_client=ws,
        db=FakeDB(),
        user_id="u",
        account_id="a",
        persist_binance_fills_db_callable=fake_persist,
        max_messages=1,
    )

    assert ws.calls == 1
    assert summary["received"] == 0
    assert summary["processed"] == 0
    assert summary["errors"] == ["receive_error"]


def test_receive_error_records_and_continues_until_max_messages():
    ws = FakeWSClient(messages=[filled_event(1001), filled_event(1002)], error_on_calls={1})
    summary = run_controlled_ws_session(
        ws_client=ws,
        db=FakeDB(),
        user_id="u",
        account_id="a",
        persist_binance_fills_db_callable=fake_persist,
        max_messages=2,
    )

    assert ws.calls == 2
    assert summary["received"] == 1
    assert summary["execution_reports"] == 1
    assert summary["inserted_candidate_count"] == 1
    assert summary["inserted_trade_ids"] == ["1002"]
    assert summary["errors"] == ["receive_error"]


def test_no_orders_or_rest_are_executed():
    class ReadOnlyClient:
        def receive(self):
            return ignored_event()

        def create_order(self):
            raise AssertionError("create_order must not be called")

        def cancel_order(self):
            raise AssertionError("cancel_order must not be called")

        def get(self):
            raise AssertionError("REST must not be called")

        def post(self):
            raise AssertionError("REST must not be called")

    summary = run_controlled_ws_session(
        ws_client=ReadOnlyClient(),
        db=FakeDB(),
        user_id="u",
        account_id="a",
        persist_binance_fills_db_callable=fake_persist,
        max_messages=1,
    )

    assert summary["received"] == 1
    assert summary["ignored"] == 1
