import os

import pytest

from apps.binance_ws.run_real_ws_controlled_session_dry_run import (
    DryRunDb,
    dry_run_noop_fill_writer,
    run_real_ws_controlled_session_dry_run,
)


class FakeWsClient:
    def __init__(self, *, api_key, private_key):
        self.api_key = api_key
        self.private_key = private_key
        self.calls = []
        self.messages = [
            {"event": {"e": "executionReport", "x": "NEW", "i": 1, "t": -1}},
        ]

    def session_logon(self):
        self.calls.append("session_logon")

    def subscribe_user_data(self):
        self.calls.append("subscribe_user_data")

    def receive(self):
        self.calls.append("receive")
        return self.messages.pop(0)

    def close(self):
        self.calls.append("close")


def test_dry_run_db_execute_returns_empty_and_no_write():
    db = DryRunDb()

    assert list(db.execute("select 1", {})) == []


def test_dry_run_persist_returns_none():
    assert dry_run_noop_fill_writer(db=object(), fills=[]) is None


def test_requires_positive_max_messages(monkeypatch):
    monkeypatch.setenv("BINANCE_WS_API_KEY", "key")
    monkeypatch.setenv("BINANCE_WS_ED25519_PRIVATE_KEY", "fake")

    with pytest.raises(ValueError, match="max_messages must be > 0"):
        run_real_ws_controlled_session_dry_run(
            max_messages=0,
            user_id="user-1",
            account_id="default",
            client_factory=lambda **kwargs: FakeWsClient(**kwargs),
        )


def test_runner_uses_client_factory_and_does_not_open_real_network(monkeypatch):
    monkeypatch.setenv("BINANCE_WS_API_KEY", "key")
    monkeypatch.setattr(
        "apps.binance_ws.run_real_ws_controlled_session_dry_run.load_ed25519_private_key_from_env",
        lambda: "private-key",
    )

    created = []

    def factory(**kwargs):
        client = FakeWsClient(**kwargs)
        created.append(client)
        return client

    result = run_real_ws_controlled_session_dry_run(
        max_messages=1,
        user_id="user-1",
        account_id="default",
        client_factory=factory,
    )

    assert len(created) == 1
    assert created[0].api_key == "key"
    assert created[0].private_key == "private-key"
    assert created[0].calls == [
        "session_logon",
        "subscribe_user_data",
        "receive",
        "close",
    ]
    assert result["received"] == 1
    assert result["execution_reports"] == 1
    assert result["not_a_fill"] == 1
    assert result["errors"] == []


def test_module_has_no_forbidden_runtime_dependencies_or_writes():
    import pathlib

    source = pathlib.Path("apps/binance_ws/run_real_ws_controlled_session_dry_run.py").read_text()

    forbidden = [
        "create_engine",
        "sessionmaker",
        "DATABASE_URL_RENDER",
        ".commit(",
        ".add(",
        # removed: false positive for parameter name
        "create_order",
        "cancel_order",
        "requests.",
        "ops.py",
    ]

    for token in forbidden:
        assert token not in source
