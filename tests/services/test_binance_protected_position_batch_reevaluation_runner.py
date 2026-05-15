from __future__ import annotations

from decimal import Decimal


def test_batch_runner_processes_each_loaded_protected_position_once():
    from apps.worker.app.engine.binance_protected_position_batch_reevaluation_runner import (
        reevaluate_active_protected_positions_once,
    )

    calls = []

    protected_positions = [
        {
            "exit_key": "exit-key-1",
            "symbol": "BTCUSDT",
            "market": "FUTURES",
            "direction": "LONG",
            "filled_qty": Decimal("0.01"),
            "avg_entry_price": Decimal("100"),
            "sl_client_algo_id": "sl-1",
            "tp_client_algo_id": "tp-1",
            "sl_status": "SUBMITTED",
            "tp_status": "SUBMITTED",
            "protection_status": "PROTECTED",
        }
    ]

    result = reevaluate_active_protected_positions_once(
        protected_positions=protected_positions,
        protection_reconciliation_by_exit_key={
            "exit-key-1": {
                "protection_state": "PROTECTED",
                "sl_classification": "ACTIVE_EVIDENCE_PRESENT",
                "tp_classification": "ACTIVE_EVIDENCE_PRESENT",
                "protection_unknown": False,
            }
        },
        sl_stop_price_by_exit_key={"exit-key-1": Decimal("90")},
        fetch_current_price=lambda symbol, market: Decimal("111"),
        run_replacement=lambda **kwargs: calls.append(kwargs) or {"status": "replaced"},
    )

    assert result == [
        {
            "exit_key": "exit-key-1",
            "result": {"status": "replaced"},
        }
    ]
    assert len(calls) == 1


def test_batch_runner_reports_blocked_context_without_replacement():
    from apps.worker.app.engine.binance_protected_position_batch_reevaluation_runner import (
        reevaluate_active_protected_positions_once,
    )

    calls = []

    protected_positions = [
        {
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
    ]

    result = reevaluate_active_protected_positions_once(
        protected_positions=protected_positions,
        protection_reconciliation_by_exit_key={
            "exit-key-1": {
                "protection_state": "PROTECTED",
                "sl_classification": "ACTIVE_EVIDENCE_PRESENT",
                "tp_classification": "ACTIVE_EVIDENCE_PRESENT",
                "protection_unknown": False,
            }
        },
        fetch_current_price=lambda symbol, market: None,
        run_replacement=lambda **kwargs: calls.append(kwargs),
    )

    assert result == [
        {
            "exit_key": "exit-key-1",
            "result": {
                "status": "blocked",
                "reason": "current_price_unavailable",
            },
        }
    ]
    assert calls == []
