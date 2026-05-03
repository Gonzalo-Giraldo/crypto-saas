import importlib
import json
import pathlib

import pytest


PACKAGE_NAME = "apps." + "binance_ws_worker"


def _import_worker_package():
    return importlib.import_module(PACKAGE_NAME)


def _import_worker_module(name):
    return importlib.import_module(PACKAGE_NAME + "." + name)


class FakeWs:
    def __init__(self, messages):
        self.messages = list(messages)

    def recv(self):
        if not self.messages:
            raise RuntimeError("no more fake messages")
        return self.messages.pop(0)


class FakeWsClient:
    def __init__(self, messages=None):
        self.ws = FakeWs(messages or [
            json.dumps({"id": "logon-id", "status": 200, "result": {"token": "hidden"}}),
            json.dumps({"id": "subscribe-id", "status": 200, "result": {"subscriptionId": 0}}),
            json.dumps({
                "subscriptionId": 0,
                "params": {"apiKey": "fixture-only"},
                "result": {"signature": "fixture-only"},
                "raw": {"private_key": "fixture-only"},
                "token": "fixture-only",
                "event": {
                    "e": "executionReport",
                    "x": "TRADE",
                    "i": 123,
                    "t": 456,
                    "s": "BTCUSDT",
                    "S": "BUY",
                    "l": "0.01",
                    "L": "50000",
                    "apiKey": "fixture-only",
                    "signature": "fixture-only",
                    "private_key": "fixture-only",
                    "secret": "fixture-only",
                    "token": "fixture-only",
                    "params": {"unsafe": True},
                    "result": {"unsafe": True},
                    "raw": {"unsafe": True},
                },
            }),
        ])
        self.calls = []

    def connect(self):
        self.calls.append("connect")

    def session_logon(self):
        self.calls.append("session_logon")

    def subscribe_user_data(self):
        self.calls.append("subscribe_user_data")

    def close(self):
        self.calls.append("close")


def test_package_import_has_no_side_effects():
    module = _import_worker_package()
    assert hasattr(module, "BinanceWsWorkerConfig")
    assert hasattr(module, "build_worker_status")


def test_default_config_is_inert_skeleton():
    config_module = _import_worker_module("config")
    config = config_module.BinanceWsWorkerConfig()
    assert config.worker_name == "binance_ws_worker"
    assert config.mode == "skeleton"


def test_skeleton_mode_is_valid_and_fully_disabled():
    config_module = _import_worker_module("config")
    status_module = _import_worker_module("status")

    status = status_module.build_worker_status(
        config_module.BinanceWsWorkerConfig(mode="skeleton")
    )

    assert status["network_enabled"] is False
    assert status["db_writes_enabled"] is False
    assert status["orders_enabled"] is False


def test_dry_run_mode_is_valid_but_still_fully_disabled():
    config_module = _import_worker_module("config")
    status_module = _import_worker_module("status")

    status = status_module.build_worker_status(
        config_module.BinanceWsWorkerConfig(mode="dry-run")
    )

    assert status["network_enabled"] is False
    assert status["db_writes_enabled"] is False
    assert status["orders_enabled"] is False


def test_main_default_no_ws_execution(capsys):
    main_module = _import_worker_module("main")

    status = main_module.main()

    captured = capsys.readouterr()

    assert "BINANCE_WS_WORKER_STATUS" in captured.out
    assert "ws_result" not in status


def test_enable_ws_requires_dry_run():
    config_module = _import_worker_module("config")
    main_module = _import_worker_module("main")

    status = main_module.main(
        config=config_module.BinanceWsWorkerConfig(mode="skeleton"),
        enable_ws=True,
    )

    assert status["ws_result"]["skipped"] is True


def test_run_ws_read_only_flow_and_order(capsys):
    main_module = _import_worker_module("main")
    fake = FakeWsClient()

    result = main_module.run_ws_read_only(
        max_events=1,
        client_builder=lambda: fake,
    )

    captured = capsys.readouterr()

    assert fake.calls == [
        "connect",
        "session_logon",
        "subscribe_user_data",
        "close",
    ]

    assert result["received"] == 1
    assert result["closed"] is True

    assert "WS_LOGON_RESPONSE_SAFE" in captured.out
    assert "WS_SUBSCRIBE_RESPONSE_SAFE" in captured.out
    assert "WS_EVENT_SAFE" in captured.out


def test_no_sensitive_tokens_in_sanitized_output(capsys):
    main_module = _import_worker_module("main")
    fake = FakeWsClient()

    main_module.run_ws_read_only(
        max_events=1,
        client_builder=lambda: fake,
    )

    captured = capsys.readouterr().out

    forbidden = [
        "apiKey",
        "signature",
        "private_key",
        "secret",
        "token",
        "params",
        "result",
        "raw",
    ]

    for token in forbidden:
        assert token not in captured


def test_safe_ws_message_allowlist_only():
    main_module = _import_worker_module("main")

    safe = main_module._safe_ws_message({
        "status": 200,
        "event": {
            "e": "executionReport",
            "x": "TRADE",
            "i": 1,
            "t": 2,
            "s": "BTCUSDT",
            "S": "BUY",
        },
    })

    assert set(safe.keys()) == {
        "message_kind",
        "status",
        "event_type",
        "execution_type",
        "order_id",
        "trade_id",
        "symbol",
        "side",
    }


def test_only_allowed_binance_ws_import_location():
    source = pathlib.Path("apps/binance_ws_worker/main.py").read_text()

    lines = [l.strip() for l in source.splitlines() if "binance_ws" in l]

    assert lines == [
        'module_name = "apps." + "binance_ws.run_real_ws_controlled_session_dry_run"'
    ]


def test_recv_only_used_inside_recv_json_object():
    source = pathlib.Path("apps/binance_ws_worker/main.py").read_text()

    func_name = "def _recv_json_object"
    start = source.find(func_name)
    assert start != -1, "_recv_json_object not found"

    # find end of function by next top-level def
    end = source.find("\ndef ", start + 1)
    if end == -1:
        end = len(source)

    recv_block = source[start:end]

    # must use recv inside the function
    assert ".recv()" in recv_block

    # everything outside the function
    outside = source[:start] + source[end:]

    # ensure recv is not used anywhere else
    assert ".recv()" not in outside

def test_forbidden_imports_and_secrets_not_present():
    files = [
        pathlib.Path("apps/binance_ws_worker/main.py"),
    ]

    forbidden = [
        "DATABASE_URL_RENDER",
        "BINANCE_API_KEY",
        "BINANCE_WS_API_KEY",
        "BINANCE_WS_ED25519_PRIVATE_KEY",
        "os.environ",
        "os.getenv",
        "sqlalchemy",
        "create_engine",
        "sessionmaker",
        "requests",
        "create_order",
        "cancel_order",
        "persist_binance_fills_db",
        "ops.py",
        "apps.api",
        "apps.binance_gateway",
    ]

    for path in files:
        text = path.read_text()
        for token in forbidden:
            assert token not in text, f"{token} found in {path}"


def test_run_ws_read_only_does_not_call_persistence_by_default():
    main_module = _import_worker_module("main")

    count = {"n": 0}

    def fake_persist(**kwargs):
        count["n"] += 1
        return {"inserted": 1, "skipped": 0}

    result = main_module.run_ws_read_only(
        max_events=1,
        client_builder=lambda: FakeWsClient(),
        persist_callable=fake_persist,
    )

    assert result["received"] == 1
    assert count["n"] == 0


def test_run_ws_read_only_requires_callable_when_persistence_enabled():
    main_module = _import_worker_module("main")

    try:
        main_module.run_ws_read_only(
            max_events=1,
            client_builder=lambda: FakeWsClient(),
            enable_persistence=True,
        )
    except ValueError as exc:
        assert "persist_callable is required" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_run_ws_read_only_calls_persistence_when_enabled():
    main_module = _import_worker_module("main")

    captured = {}

    def fake_persist(**kwargs):
        captured.update(kwargs)
        return {"inserted": 1, "skipped": 0}

    result = main_module.run_ws_read_only(
        max_events=1,
        client_builder=lambda: FakeWsClient(),
        enable_persistence=True,
        persist_callable=fake_persist,
    )

    assert result["received"] == 1
    assert captured["db"] is None
    assert captured["user_id"] == ""
    assert captured["account_id"] == ""
    assert captured["fills"][0]["tradeId"] == "456"
    assert captured["fills"][0]["orderId"] == "123"
    assert captured["fills"][0]["qty"] == "0.01"
    assert captured["fills"][0]["price"] == "50000"
