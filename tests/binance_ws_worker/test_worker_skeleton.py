import importlib
import pathlib

import pytest


PACKAGE_NAME = "apps." + "binance_ws_worker"


def _import_worker_package():
    return importlib.import_module(PACKAGE_NAME)


def _import_worker_module(name):
    return importlib.import_module(PACKAGE_NAME + "." + name)


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

    assert status == {
        "worker_name": "binance_ws_worker",
        "mode": "skeleton",
        "network_enabled": False,
        "db_writes_enabled": False,
        "orders_enabled": False,
        "broker_actions_enabled": False,
        "persistence_enabled": False,
    }


def test_dry_run_mode_is_valid_but_still_fully_disabled():
    config_module = _import_worker_module("config")
    status_module = _import_worker_module("status")

    status = status_module.build_worker_status(
        config_module.BinanceWsWorkerConfig(mode="dry-run")
    )

    assert status == {
        "worker_name": "binance_ws_worker",
        "mode": "dry-run",
        "network_enabled": False,
        "db_writes_enabled": False,
        "orders_enabled": False,
        "broker_actions_enabled": False,
        "persistence_enabled": False,
    }


def test_invalid_mode_rejected():
    config_module = _import_worker_module("config")
    status_module = _import_worker_module("status")

    config = config_module.BinanceWsWorkerConfig(mode="live")

    with pytest.raises(ValueError, match="mode must be one of: dry-run, skeleton"):
        status_module.build_worker_status(config)


def test_main_only_prints_status(capsys):
    main_module = _import_worker_module("main")

    status = main_module.main()

    captured = capsys.readouterr()

    assert "BINANCE_WS_WORKER_STATUS" in captured.out
    assert '"worker_name": "binance_ws_worker"' in captured.out
    assert '"mode": "skeleton"' in captured.out
    assert '"network_enabled": false' in captured.out
    assert '"db_writes_enabled": false' in captured.out
    assert '"orders_enabled": false' in captured.out
    assert status["network_enabled"] is False
    assert status["db_writes_enabled"] is False
    assert status["orders_enabled"] is False


def test_worker_files_do_not_import_forbidden_dependencies_or_read_secrets():
    files = [
        pathlib.Path("apps/binance_ws_worker/__init__.py"),
        pathlib.Path("apps/binance_ws_worker/config.py"),
        pathlib.Path("apps/binance_ws_worker/status.py"),
        pathlib.Path("apps/binance_ws_worker/main.py"),
    ]

    forbidden = [
        "apps" + ".binance_ws",
        "apps" + ".api",
        "apps" + ".binance_gateway",
        "ops" + ".py",
        "DATABASE_URL_RENDER",
        "BINANCE_API_KEY",
        "BINANCE_WS_API_KEY",
        "BINANCE_WS_ED25519_PRIVATE_KEY",
        "os" + ".environ",
        "os" + ".getenv",
        "apiKey",
        "signature",
        "private_key",
        "secret=",
        "secret:",
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
    ]

    for path in files:
        source = path.read_text()
        for token in forbidden:
            assert token not in source, f"{token} found in {path}"
