from __future__ import annotations

from decimal import Decimal


def test_builds_runtime_context_from_protected_position_row_and_current_price():
    from apps.worker.app.engine.binance_protected_position_runtime_context import (
        build_protected_position_runtime_context,
    )

    row = {
        "exit_key": "exit-key-1",
        "symbol": "BTCUSDT",
        "market": "FUTURES",
        "direction": "LONG",
        "filled_qty": Decimal("0.01"),
        "avg_entry_price": Decimal("100"),
        "sl_client_algo_id": "sl-1",
        "protection_status": "PROTECTED",
        "sl_status": "SUBMITTED",
    }

    result = build_protected_position_runtime_context(
        protected_position=row,
        fetch_current_price=lambda symbol, market: Decimal("111"),
    )

    assert result == {
        "exit_key": "exit-key-1",
        "old_sl_client_algo_id": "sl-1",
        "position": {
            "symbol": "BTCUSDT",
            "side": "BUY",
            "direction": "LONG",
            "entry_price": Decimal("100"),
            "stop_loss": None,
            "current_price": Decimal("111"),
            "qty": Decimal("0.01"),
            "intent_entry_price": Decimal("100"),
        },
    }


def test_context_builder_fails_closed_when_price_missing():
    from apps.worker.app.engine.binance_protected_position_runtime_context import (
        build_protected_position_runtime_context,
    )

    row = {
        "exit_key": "exit-key-1",
        "symbol": "BTCUSDT",
        "market": "FUTURES",
        "direction": "LONG",
        "filled_qty": Decimal("0.01"),
        "avg_entry_price": Decimal("100"),
        "sl_client_algo_id": "sl-1",
    }

    assert build_protected_position_runtime_context(
        protected_position=row,
        fetch_current_price=lambda symbol, market: None,
    ) == {
        "status": "blocked",
        "reason": "current_price_unavailable",
    }


def test_context_builder_rejects_non_futures_market():
    from apps.worker.app.engine.binance_protected_position_runtime_context import (
        build_protected_position_runtime_context,
    )

    row = {
        "exit_key": "exit-key-1",
        "symbol": "BTCUSDT",
        "market": "SPOT",
        "direction": "LONG",
        "filled_qty": Decimal("0.01"),
        "avg_entry_price": Decimal("100"),
        "sl_client_algo_id": "sl-1",
    }

    assert build_protected_position_runtime_context(
        protected_position=row,
        fetch_current_price=lambda symbol, market: Decimal("111"),
    ) == {
        "status": "blocked",
        "reason": "market_must_be_FUTURES",
    }
