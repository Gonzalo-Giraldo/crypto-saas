from __future__ import annotations


def test_runtime_gate_allows_only_protected_active_sl_with_candidate():
    from apps.worker.app.engine.binance_trailing_stop_runtime_gate import (
        can_run_trailing_stop_replacement,
    )

    result = can_run_trailing_stop_replacement(
        protection_reconciliation={
            "protection_state": "PROTECTED",
            "sl_classification": "ACTIVE_EVIDENCE_PRESENT",
            "tp_classification": "ACTIVE_EVIDENCE_PRESENT",
            "protection_unknown": False,
        },
        trailing_decision={
            "symbol": "BTCUSDT",
            "old_sl": "90",
            "new_sl": "100",
        },
        old_sl_client_algo_id="old-sl-1",
        transition_claim={
            "claim_status": "ACTIVE",
            "owner_id": "worker-1",
        },
    )
    assert result == {
        "allowed": True,
        "reason": "trailing_replacement_allowed",
    }


def test_runtime_gate_blocks_unknown_protection():
    from apps.worker.app.engine.binance_trailing_stop_runtime_gate import (
        can_run_trailing_stop_replacement,
    )

    result = can_run_trailing_stop_replacement(
        protection_reconciliation={
            "protection_state": "UNKNOWN",
            "sl_classification": "UNKNOWN",
            "tp_classification": "ACTIVE_EVIDENCE_PRESENT",
            "protection_unknown": True,
        },
        trailing_decision={
            "symbol": "BTCUSDT",
            "old_sl": "90",
            "new_sl": "100",
        },
        old_sl_client_algo_id="old-sl-1",
        transition_claim={
            "claim_status": "ACTIVE",
            "owner_id": "worker-1",
        },
    )

    assert result == {
        "allowed": False,
        "reason": "protection_not_authoritative",
    }


def test_runtime_gate_blocks_without_active_sl_evidence():
    from apps.worker.app.engine.binance_trailing_stop_runtime_gate import (
        can_run_trailing_stop_replacement,
    )

    result = can_run_trailing_stop_replacement(
        protection_reconciliation={
            "protection_state": "PROTECTED",
            "sl_classification": "UNKNOWN",
            "tp_classification": "ACTIVE_EVIDENCE_PRESENT",
            "protection_unknown": False,
        },
        trailing_decision={
            "symbol": "BTCUSDT",
            "old_sl": "90",
            "new_sl": "100",
        },
        old_sl_client_algo_id="old-sl-1",
        transition_claim={
            "claim_status": "ACTIVE",
            "owner_id": "worker-1",
        },
    )
    assert result == {
        "allowed": False,
        "reason": "sl_not_authoritative_active",
    }

def test_runtime_gate_blocks_without_trailing_candidate():
    from apps.worker.app.engine.binance_trailing_stop_runtime_gate import (
        can_run_trailing_stop_replacement,
    )

    result = can_run_trailing_stop_replacement(
        protection_reconciliation={
            "protection_state": "PROTECTED",
            "sl_classification": "ACTIVE_EVIDENCE_PRESENT",
            "tp_classification": "ACTIVE_EVIDENCE_PRESENT",
            "protection_unknown": False,
        },
        trailing_decision=None,
        old_sl_client_algo_id="old-sl-1",
        transition_claim={
            "claim_status": "ACTIVE",
            "owner_id": "worker-1",
        },
    )

    assert result == {
        "allowed": False,
        "reason": "no_trailing_candidate",
    }

def test_runtime_gate_blocks_without_old_sl_client_algo_id():
    from apps.worker.app.engine.binance_trailing_stop_runtime_gate import (
        can_run_trailing_stop_replacement,
    )

    result = can_run_trailing_stop_replacement(
        protection_reconciliation={
            "protection_state": "PROTECTED",
            "sl_classification": "ACTIVE_EVIDENCE_PRESENT",
            "tp_classification": "ACTIVE_EVIDENCE_PRESENT",
            "protection_unknown": False,
        },
        trailing_decision={
            "symbol": "BTCUSDT",
            "old_sl": "90",
            "new_sl": "100",
        },
        old_sl_client_algo_id="",
        transition_claim={
            "claim_status": "ACTIVE",
            "owner_id": "worker-1",
        },
    )

    assert result == {
        "allowed": False,
        "reason": "old_sl_client_algo_id_required",
    }

def test_runtime_gate_blocks_without_active_transition_claim():
    from apps.worker.app.engine.binance_trailing_stop_runtime_gate import (
        can_run_trailing_stop_replacement,
    )

    result = can_run_trailing_stop_replacement(
        protection_reconciliation={
            "protection_state": "PROTECTED",
            "sl_classification": "ACTIVE_EVIDENCE_PRESENT",
            "tp_classification": "ACTIVE_EVIDENCE_PRESENT",
            "protection_unknown": False,
        },
        trailing_decision={
            "symbol": "BTCUSDT",
            "old_sl": "90",
            "new_sl": "100",
        },
        old_sl_client_algo_id="old-sl-1",
        transition_claim=None,
    )

    assert result == {
        "allowed": False,
        "reason": "active_transition_claim_required",
    }
