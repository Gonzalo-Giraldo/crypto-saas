from __future__ import annotations

def test_runner_evaluates_trailing_only_after_authoritative_protection():
    from apps.worker.app.engine.binance_protected_position_reevaluation_runner import (
        reevaluate_protected_position_once,
    )

    calls = []

    result = reevaluate_protected_position_once(
        position={
            "symbol": "BTCUSDT",
            "side": "BUY",
            "direction": "LONG",
            "entry_price": "100",
            "stop_loss": "90",
            "current_price": "111",
            "qty": "0.01",
            "intent_entry_price": "100",
        },
        protection_reconciliation={
            "protection_state": "PROTECTED",
            "sl_classification": "ACTIVE_EVIDENCE_PRESENT",
            "tp_classification": "ACTIVE_EVIDENCE_PRESENT",
            "protection_unknown": False,
        },
        old_sl_client_algo_id="old-sl-1",
        replacement_client_order_id="trail-1",
        transition_claim={
            "claim_status": "ACTIVE",
            "owner_id": "worker-1",
        },
        run_replacement=lambda **kwargs: (
            calls.append(kwargs) or {"status": "replaced"}
        ),
    )

    assert result["status"] == "replaced"
    assert calls

def test_runner_noops_when_protection_not_authoritative():
    from apps.worker.app.engine.binance_protected_position_reevaluation_runner import (
        reevaluate_protected_position_once,
    )

    calls = []

    result = reevaluate_protected_position_once(
        position={
            "symbol": "BTCUSDT",
            "side": "BUY",
            "direction": "LONG",
            "entry_price": "100",
            "stop_loss": "90",
            "current_price": "111",
            "qty": "0.01",
        },
        protection_reconciliation={
            "protection_state": "UNKNOWN",
            "sl_classification": "UNKNOWN",
            "tp_classification": "ACTIVE_EVIDENCE_PRESENT",
            "protection_unknown": True,
        },
        old_sl_client_algo_id="old-sl-1",
        replacement_client_order_id="trail-1",
        transition_claim={
            "claim_status": "ACTIVE",
            "owner_id": "worker-1",
        },
        run_replacement=lambda **kwargs: calls.append(kwargs),
    )

    assert result == {
        "status": "blocked",
        "reason": "protection_not_authoritative",
    }

    assert calls == []

def test_runner_blocks_without_active_transition_claim():
    from apps.worker.app.engine.binance_protected_position_reevaluation_runner import (
        reevaluate_protected_position_once,
    )

    calls = []

    result = reevaluate_protected_position_once(
        position={
            "symbol": "BTCUSDT",
            "side": "BUY",
            "direction": "LONG",
            "entry_price": "100",
            "stop_loss": "90",
            "current_price": "111",
            "qty": "0.01",
            "intent_entry_price": "100",
        },
        protection_reconciliation={
            "protection_state": "PROTECTED",
            "sl_classification": "ACTIVE_EVIDENCE_PRESENT",
            "tp_classification": "ACTIVE_EVIDENCE_PRESENT",
            "protection_unknown": False,
        },
        old_sl_client_algo_id="old-sl-1",
        replacement_client_order_id="trail-1",
        transition_claim=None,
        run_replacement=lambda **kwargs: calls.append(kwargs) or {"status": "replaced"},
    )

    assert result == {
        "status": "blocked",
        "reason": "active_transition_claim_required",
    }
    assert calls == []
