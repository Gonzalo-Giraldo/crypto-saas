from __future__ import annotations

from decimal import Decimal

from apps.worker.app.engine.binance_exit_guard import (
    build_binance_exit_key,
    guard_binance_exit,
)


def test_spot_long_trailing_stop_allows_sell_when_not_duplicate():
    result = guard_binance_exit(
        market="FUTURES",
        position_direction="LONG",
        symbol="BTCUSDT",
        net_qty="0.1",
        intent_id="intent-1",
        exit_reason="TRAILING_STOP",
        current_sl="90",
        new_sl="100",
        is_duplicate_exit=lambda exit_key: False,
    )

    assert result.allowed is True
    assert result.reason == "ALLOWED"
    assert result.exit_side == "SELL"
    assert result.qty == Decimal("0.1")
    assert result.exit_key == "BINANCE_EXIT|LONG|BTCUSDT|intent-1|TRAILING_STOP"


def test_futures_short_trailing_stop_allows_buy_when_not_duplicate():
    result = guard_binance_exit(
        market="FUTURES",
        position_direction="SHORT",
        symbol="BTCUSDT",
        net_qty="0.1",
        intent_id="intent-1",
        exit_reason="TRAILING_STOP",
        current_sl="120",
        new_sl="110",
        is_duplicate_exit=lambda exit_key: False,
    )

    assert result.allowed is True
    assert result.reason == "ALLOWED"
    assert result.exit_side == "BUY"
    assert result.qty == Decimal("0.1")


def test_net_qty_zero_blocks():
    result = guard_binance_exit(
        market="FUTURES",
        position_direction="LONG",
        symbol="BTCUSDT",
        net_qty="0",
        intent_id="intent-1",
        exit_reason="STOP_LOSS",
        is_duplicate_exit=lambda exit_key: False,
    )

    assert result.allowed is False
    assert result.reason == "INVALID_NET_QTY"


def test_duplicate_blocks():
    result = guard_binance_exit(
        market="FUTURES",
        position_direction="LONG",
        symbol="BTCUSDT",
        net_qty="0.1",
        intent_id="intent-1",
        exit_reason="STOP_LOSS",
        is_duplicate_exit=lambda exit_key: True,
    )

    assert result.allowed is False
    assert result.reason == "DUPLICATE_EXIT"
    assert result.exit_key == "BINANCE_EXIT|LONG|BTCUSDT|intent-1|STOP_LOSS"


def test_trailing_without_new_sl_blocks():
    result = guard_binance_exit(
        market="FUTURES",
        position_direction="LONG",
        symbol="BTCUSDT",
        net_qty="0.1",
        intent_id="intent-1",
        exit_reason="TRAILING_STOP",
        current_sl="90",
        new_sl=None,
        is_duplicate_exit=lambda exit_key: False,
    )

    assert result.allowed is False
    assert result.reason == "MISSING_TRAILING_STOP"


def test_trailing_with_non_favorable_new_sl_blocks():
    result = guard_binance_exit(
        market="FUTURES",
        position_direction="LONG",
        symbol="BTCUSDT",
        net_qty="0.1",
        intent_id="intent-1",
        exit_reason="TRAILING_STOP",
        current_sl="90",
        new_sl="90",
        is_duplicate_exit=lambda exit_key: False,
    )

    assert result.allowed is False
    assert result.reason == "NON_FAVORABLE_TRAILING_STOP"


def test_spot_contract_blocks():
    result = guard_binance_exit(
        market="SPOT",
        position_direction="LONG",
        symbol="BTCUSDT",
        net_qty="0.1",
        intent_id="intent-1",
        exit_reason="STOP_LOSS",
        is_duplicate_exit=lambda exit_key: False,
    )

    assert result.allowed is False
    assert result.reason.startswith("INVALID_CONTRACT")
    assert result.exit_side is None


def test_exit_key_is_deterministic():
    first = build_binance_exit_key(
        market="spot",
        position_direction="long",
        symbol="btcusdt",
        intent_id="intent-1",
        exit_reason="trailing_stop",
    )
    second = build_binance_exit_key(
        market="FUTURES",
        position_direction="LONG",
        symbol="BTCUSDT",
        intent_id="intent-1",
        exit_reason="TRAILING_STOP",
    )

    assert first == second


def test_no_write_or_order_dependencies():
    import apps.worker.app.engine.binance_exit_guard as module

    source = module.__loader__.get_source(module.__name__)

    forbidden = [
        "ops.py",
        "apps.api.app.api.ops",
        "send_order_real",
        "cancel_order",
        "db.commit",
        "db.add",
        "INSERT",
        "UPDATE",
        "DELETE",
    ]

    for item in forbidden:
        assert item not in source
