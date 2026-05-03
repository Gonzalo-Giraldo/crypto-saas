import importlib
import pathlib

import pytest

from apps.binance_ws_worker.config import BinanceWsWorkerConfig
from apps.binance_ws_worker.main import build_worker_status, main


def test_package_import_has_no_side_effects():
    module = importlib.import_module("apps.binance_ws_worker")

    assert hasattr(module, "BinanceWsWorkerConfig")
    assert hasattr(module, "build_worker_status")
    assert hasattr(module, "main")


def test_default_worker_status_is_dry_run_and_safe():
    status = build_worker_status()

    assert status == {
        "worker_name": "binance_ws_worker",
        "mode": "dry-run",
        "safe_to_run": True,
        "live_enabled": False,
        "network_enabled": False,
        "db_writes_enabled": False,
        "orders_enabled": False,
    }


def test_live_mode_requires_explicit_enable():
    config = BinanceWsWorkerConfig(mode="live", live_enabled=False)

    with pytest.raises(RuntimeError, match="live mode requires explicit live_enabled=True"):
        build_worker_status(config)


def test_live_mode_can_be_constructed_only_with_explicit_enable_but_is_not_safe_to_run():
    config = BinanceWsWorkerConfig(mode="live", live_enabled=True)

    status = build_worker_status(config)

    assert status["mode"] == "live"
    assert status["safe_to_run"] is False
    assert status["live_enabled"] is True
    assert status["network_enabled"] is False
    assert status["db_writes_enabled"] is False
    assert status["orders_enabled"] is False


def test_invalid_mode_rejected():
    config = BinanceWsWorkerConfig(mode="invalid")

    with pytest.raises(ValueError, match="mode must be 'dry-run' or 'live'"):
        build_worker_status(config)


def test_main_prints_safe_status(capsys):
    status = main()

    captured = capsys.readouterr()

    assert "BINANCE_WS_WORKER_STATUS" in captured.out
    assert '"mode": "dry-run"' in captured.out
    assert '"safe_to_run": true' in captured.out
    assert status["safe_to_run"] is True


def test_worker_modules_do_not_import_forbidden_dependencies_or_read_secrets():
    files = [
        pathlib.Path("apps/binance_ws_worker/__init__.py"),
        pathlib.Path("apps/binance_ws_worker/config.py"),
        pathlib.Path("apps/binance_ws_worker/main.py"),
    ]

    forbidden = [
        "DATABASE_URL_RENDER",
        "BINANCE_API_KEY",
        "BINANCE_WS_API_KEY",
        "BINANCE_WS_ED25519_PRIVATE_KEY",
        "os.environ",
        "sqlalchemy",
        "create_engine",
        "sessionmaker",
        "websocket",
        "create_connection",
        "requests",
        "FastAPI",
        "uvicorn",
        "create_order",
        "cancel_order",
        "persist_binance_fills_db",
        "ops.py",
        "apps.binance_gateway",
        "apps.api",
    ]

    for path in files:
        source = path.read_text()
        for token in forbidden:
            assert token not in source, f"{token} found in {path}"
