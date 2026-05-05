from __future__ import annotations

import pytest

from apps.worker.app.engine.binance_exit_contract import (
    BinanceExitReason,
    BinanceMarket,
    BinanceOrderSide,
    BinancePositionDirection,
    build_binance_exit_contract,
)


def test_futures_long_contract_enters_buy_exits_sell_reduce_only():
    contract = build_binance_exit_contract(
        market="FUTURES",
        position_direction="LONG",
        exit_reason="STOP_LOSS",
    )

    assert contract.market == BinanceMarket.FUTURES
    assert contract.position_direction == BinancePositionDirection.LONG
    assert contract.entry_side == BinanceOrderSide.BUY
    assert contract.exit_side == BinanceOrderSide.SELL
    assert contract.exit_reason == BinanceExitReason.STOP_LOSS
    assert contract.reduce_only is True


def test_futures_short_contract_enters_sell_exits_buy_reduce_only():
    contract = build_binance_exit_contract(
        market="FUTURES",
        position_direction="SHORT",
        exit_reason="TAKE_PROFIT",
    )

    assert contract.market == BinanceMarket.FUTURES
    assert contract.position_direction == BinancePositionDirection.SHORT
    assert contract.entry_side == BinanceOrderSide.SELL
    assert contract.exit_side == BinanceOrderSide.BUY
    assert contract.exit_reason == BinanceExitReason.TAKE_PROFIT
    assert contract.reduce_only is True


def test_trailing_stop_exit_reason_is_allowed_for_futures_long():
    contract = build_binance_exit_contract(
        market="FUTURES",
        position_direction="LONG",
        exit_reason="TRAILING_STOP",
    )

    assert contract.exit_reason == BinanceExitReason.TRAILING_STOP
    assert contract.reduce_only is True


def test_spot_is_rejected():
    with pytest.raises(ValueError):
        build_binance_exit_contract(
            market="SPOT",
            position_direction="LONG",
            exit_reason="STOP_LOSS",
        )


def test_invalid_exit_reason_is_blocked():
    with pytest.raises(ValueError):
        build_binance_exit_contract(
            market="FUTURES",
            position_direction="LONG",
            exit_reason="MANUAL_EXIT",
        )


def test_no_write_or_order_dependencies():
    import apps.worker.app.engine.binance_exit_contract as module

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
