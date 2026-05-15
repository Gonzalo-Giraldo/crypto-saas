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
        owner_id="worker-1",
        claim_transition=lambda **kwargs: {"status": "claimed"},
        run_replacement=lambda **kwargs: (
            calls.append(kwargs) or {"status": "replaced"}
        ),
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


def test_batch_runner_claims_trailing_transition_before_replacement():
    from decimal import Decimal
    from apps.worker.app.engine.binance_protected_position_batch_reevaluation_runner import (
        reevaluate_active_protected_positions_once,
    )

    calls = []

    protected_positions = [
        {
            "exit_key": "exit-key-claim-1",
            "symbol": "BTCUSDT",
            "market": "FUTURES",
            "direction": "LONG",
            "filled_qty": Decimal("0.01"),
            "avg_entry_price": Decimal("100"),
            "sl_client_algo_id": "sl-claim-1",
            "tp_client_algo_id": "tp-claim-1",
            "sl_status": "SUBMITTED",
            "tp_status": "SUBMITTED",
            "protection_status": "PROTECTED",
        }
    ]

    def fake_claim(**kwargs):
        calls.append(("claim", kwargs))
        return {"status": "claimed"}

    def fake_replace(**kwargs):
        calls.append(("replace", kwargs))
        return {"status": "replaced"}

    result = reevaluate_active_protected_positions_once(
        protected_positions=protected_positions,
        protection_reconciliation_by_exit_key={
            "exit-key-claim-1": {
                "protection_state": "PROTECTED",
                "sl_classification": "ACTIVE_EVIDENCE_PRESENT",
                "tp_classification": "ACTIVE_EVIDENCE_PRESENT",
                "protection_unknown": False,
            }
        },
        sl_stop_price_by_exit_key={"exit-key-claim-1": Decimal("90")},
        fetch_current_price=lambda symbol, market: Decimal("111"),
        owner_id="worker-1",
        claim_transition=fake_claim,
        run_replacement=fake_replace,
    )

    assert result == [
        {
            "exit_key": "exit-key-claim-1",
            "result": {"status": "replaced"},
        }
    ]

    assert calls[0] == (
        "claim",
        {
            "exit_key": "exit-key-claim-1",
            "required_action": "ACTION_ACTIVATE_TRAILING",
            "owner_id": "worker-1",
        },
    )

    replace_calls = [
        call for call in calls
        if call[0] == "replace"
    ]

    assert len(replace_calls) == 1

def test_batch_runner_blocks_replacement_when_claim_is_not_owned():
    from decimal import Decimal
    from apps.worker.app.engine.binance_protected_position_batch_reevaluation_runner import (
        reevaluate_active_protected_positions_once,
    )

    calls = []

    protected_positions = [
        {
            "exit_key": "exit-key-claim-2",
            "symbol": "BTCUSDT",
            "market": "FUTURES",
            "direction": "LONG",
            "filled_qty": Decimal("0.01"),
            "avg_entry_price": Decimal("100"),
            "sl_client_algo_id": "sl-claim-2",
            "tp_client_algo_id": "tp-claim-2",
            "sl_status": "SUBMITTED",
            "tp_status": "SUBMITTED",
            "protection_status": "PROTECTED",
        }
    ]

    def fake_claim(**kwargs):
        calls.append(("claim", kwargs))
        return {"status": "blocked", "reason": "transition_claim_already_owned"}

    result = reevaluate_active_protected_positions_once(
        protected_positions=protected_positions,
        protection_reconciliation_by_exit_key={
            "exit-key-claim-2": {
                "protection_state": "PROTECTED",
                "sl_classification": "ACTIVE_EVIDENCE_PRESENT",
                "tp_classification": "ACTIVE_EVIDENCE_PRESENT",
                "protection_unknown": False,
            }
        },
        sl_stop_price_by_exit_key={"exit-key-claim-2": Decimal("90")},
        fetch_current_price=lambda symbol, market: Decimal("111"),
        owner_id="worker-2",
        claim_transition=fake_claim,
        run_replacement=lambda **kwargs: calls.append(("replace", kwargs)),
    )

    assert result == [
        {
            "exit_key": "exit-key-claim-2",
            "result": {
                "status": "blocked",
                "reason": "transition_claim_not_owned",
            },
        }
    ]
    assert calls == [
        (
            "claim",
            {
                "exit_key": "exit-key-claim-2",
                "required_action": "ACTION_ACTIVATE_TRAILING",
                "owner_id": "worker-2",
            },
        )
    ]


def test_batch_runner_completes_claim_as_finalized_after_replacement_success():
    from decimal import Decimal
    from apps.worker.app.engine.binance_protected_position_batch_reevaluation_runner import (
        reevaluate_active_protected_positions_once,
    )

    calls = []

    result = reevaluate_active_protected_positions_once(
        protected_positions=[
            {
                "exit_key": "exit-key-complete-1",
                "symbol": "BTCUSDT",
                "market": "FUTURES",
                "direction": "LONG",
                "filled_qty": Decimal("0.01"),
                "avg_entry_price": Decimal("100"),
                "sl_client_algo_id": "sl-complete-1",
                "tp_client_algo_id": "tp-complete-1",
                "sl_status": "SUBMITTED",
                "tp_status": "SUBMITTED",
                "protection_status": "PROTECTED",
            }
        ],
        protection_reconciliation_by_exit_key={
            "exit-key-complete-1": {
                "protection_state": "PROTECTED",
                "sl_classification": "ACTIVE_EVIDENCE_PRESENT",
                "tp_classification": "ACTIVE_EVIDENCE_PRESENT",
                "protection_unknown": False,
            }
        },
        sl_stop_price_by_exit_key={"exit-key-complete-1": Decimal("90")},
        fetch_current_price=lambda symbol, market: Decimal("111"),
        owner_id="worker-1",
        claim_transition=lambda **kwargs: calls.append(("claim", kwargs)) or {"status": "claimed"},
        complete_transition=lambda **kwargs: calls.append(("complete", kwargs)) or {"status": kwargs["final_status"]},
        run_replacement=lambda **kwargs: calls.append(("replace", kwargs)) or {"status": "replaced"},
    )

    assert result == [
        {
            "exit_key": "exit-key-complete-1",
            "result": {"status": "replaced"},
        }
    ]

    assert calls[-1] == (
        "complete",
        {
            "exit_key": "exit-key-complete-1",
            "required_action": "ACTION_ACTIVATE_TRAILING",
            "owner_id": "worker-1",
            "final_status": "FINALIZED",
        },
    )


def test_batch_runner_completes_claim_as_abandoned_after_blocked_result():
    from decimal import Decimal
    from apps.worker.app.engine.binance_protected_position_batch_reevaluation_runner import (
        reevaluate_active_protected_positions_once,
    )

    calls = []

    result = reevaluate_active_protected_positions_once(
        protected_positions=[
            {
                "exit_key": "exit-key-complete-2",
                "symbol": "BTCUSDT",
                "market": "FUTURES",
                "direction": "LONG",
                "filled_qty": Decimal("0.01"),
                "avg_entry_price": Decimal("100"),
                "sl_client_algo_id": "sl-complete-2",
                "tp_client_algo_id": "tp-complete-2",
                "sl_status": "SUBMITTED",
                "tp_status": "SUBMITTED",
                "protection_status": "PROTECTED",
            }
        ],
        protection_reconciliation_by_exit_key={
            "exit-key-complete-2": {
                "protection_state": "PROTECTED",
                "sl_classification": "ACTIVE_EVIDENCE_PRESENT",
                "tp_classification": "ACTIVE_EVIDENCE_PRESENT",
                "protection_unknown": False,
            }
        },
        sl_stop_price_by_exit_key={"exit-key-complete-2": Decimal("90")},
        fetch_current_price=lambda symbol, market: Decimal("111"),
        owner_id="worker-1",
        claim_transition=lambda **kwargs: calls.append(("claim", kwargs)) or {"status": "claimed"},
        complete_transition=lambda **kwargs: calls.append(("complete", kwargs)) or {"status": kwargs["final_status"]},
        run_replacement=lambda **kwargs: calls.append(("replace", kwargs)) or {
            "status": "blocked",
            "reason": "replacement_sl_not_active",
        },
    )

    assert result == [
        {
            "exit_key": "exit-key-complete-2",
            "result": {
                "status": "blocked",
                "reason": "replacement_sl_not_active",
            },
        }
    ]

    assert calls[-1] == (
        "complete",
        {
            "exit_key": "exit-key-complete-2",
            "required_action": "ACTION_ACTIVATE_TRAILING",
            "owner_id": "worker-1",
            "final_status": "ABANDONED",
        },
    )


def test_batch_runner_abandons_claim_when_replacement_raises_after_claim():
    from decimal import Decimal
    from apps.worker.app.engine.binance_protected_position_batch_reevaluation_runner import (
        reevaluate_active_protected_positions_once,
    )

    calls = []

    def raise_after_claim(**kwargs):
        calls.append(("replace", kwargs))
        raise RuntimeError("replacement_runtime_error")

    result = reevaluate_active_protected_positions_once(
        protected_positions=[
            {
                "exit_key": "exit-key-exception-1",
                "symbol": "BTCUSDT",
                "market": "FUTURES",
                "direction": "LONG",
                "filled_qty": Decimal("0.01"),
                "avg_entry_price": Decimal("100"),
                "sl_client_algo_id": "sl-exception-1",
                "tp_client_algo_id": "tp-exception-1",
                "sl_status": "SUBMITTED",
                "tp_status": "SUBMITTED",
                "protection_status": "PROTECTED",
            }
        ],
        protection_reconciliation_by_exit_key={
            "exit-key-exception-1": {
                "protection_state": "PROTECTED",
                "sl_classification": "ACTIVE_EVIDENCE_PRESENT",
                "tp_classification": "ACTIVE_EVIDENCE_PRESENT",
                "protection_unknown": False,
            }
        },
        sl_stop_price_by_exit_key={"exit-key-exception-1": Decimal("90")},
        fetch_current_price=lambda symbol, market: Decimal("111"),
        owner_id="worker-1",
        claim_transition=lambda **kwargs: calls.append(("claim", kwargs)) or {"status": "claimed"},
        complete_transition=lambda **kwargs: calls.append(("complete", kwargs)) or {"status": kwargs["final_status"]},
        run_replacement=raise_after_claim,
    )

    assert result == [
        {
            "exit_key": "exit-key-exception-1",
            "result": {
                "status": "blocked",
                "reason": "protected_position_reevaluation_error",
                "error": "replacement_runtime_error",
            },
        }
    ]

    assert calls[-1] == (
        "complete",
        {
            "exit_key": "exit-key-exception-1",
            "required_action": "ACTION_ACTIVATE_TRAILING",
            "owner_id": "worker-1",
            "final_status": "ABANDONED",
        },
    )

def test_batch_runner_abandons_claim_when_complete_transition_raises():
    from decimal import Decimal

    from apps.worker.app.engine.binance_protected_position_batch_reevaluation_runner import (
        reevaluate_active_protected_positions_once,
    )

    calls = []

    def fake_claim(**kwargs):
        calls.append(("claim", kwargs))
        return {"status": "claimed"}

    def fake_replace(**kwargs):
        calls.append(("replace", kwargs))
        return {"status": "replaced"}

    def fake_complete(**kwargs):
        calls.append(("complete", kwargs))
        raise RuntimeError("db_commit_failed")

    result = reevaluate_active_protected_positions_once(
        protected_positions=[
            {
                "exit_key": "exit-key-complete-exception",
                "symbol": "BTCUSDT",
                "market": "FUTURES",
                "direction": "LONG",
                "filled_qty": Decimal("0.01"),
                "avg_entry_price": Decimal("100"),
                "sl_client_algo_id": "sl-complete-exception",
                "tp_client_algo_id": "tp-complete-exception",
                "sl_status": "SUBMITTED",
                "tp_status": "SUBMITTED",
                "protection_status": "PROTECTED",
            }
        ],
        protection_reconciliation_by_exit_key={
            "exit-key-complete-exception": {
                "protection_state": "PROTECTED",
                "sl_classification": "ACTIVE_EVIDENCE_PRESENT",
                "tp_classification": "ACTIVE_EVIDENCE_PRESENT",
                "protection_unknown": False,
            }
        },
        sl_stop_price_by_exit_key={
            "exit-key-complete-exception": Decimal("90")
        },
        fetch_current_price=lambda symbol, market: Decimal("111"),
        owner_id="worker-1",
        claim_transition=fake_claim,
        complete_transition=fake_complete,
        run_replacement=fake_replace,
    )

    assert result == [
        {
            "exit_key": "exit-key-complete-exception",
            "result": {
                "status": "blocked",
                "reason": "protected_position_reevaluation_error",
                "error": "db_commit_failed",
                "lifecycle_cleanup_error": "db_commit_failed",
            },
        }
    ]

    claim_calls = [
        call for call in calls
        if call[0] == "claim"
    ]

    replace_calls = [
        call for call in calls
        if call[0] == "replace"
    ]

    complete_calls = [
        call for call in calls
        if call[0] == "complete"
    ]

    assert len(claim_calls) >= 1
    assert len(replace_calls) == 1
    assert len(complete_calls) >= 1

def test_batch_runner_acquires_transition_claim_only_once_per_position():
    from decimal import Decimal
    from apps.worker.app.engine.binance_protected_position_batch_reevaluation_runner import (
        reevaluate_active_protected_positions_once,
    )

    calls = []

    def fake_claim(**kwargs):
        calls.append(("claim", kwargs))
        if len([call for call in calls if call[0] == "claim"]) == 1:
            return {"status": "claimed"}
        return {"status": "already_owned"}

    def fake_replace(**kwargs):
        calls.append(("replace", kwargs))
        return {"status": "replaced"}

    result = reevaluate_active_protected_positions_once(
        protected_positions=[
            {
                "exit_key": "exit-key-single-claim",
                "symbol": "BTCUSDT",
                "market": "FUTURES",
                "direction": "LONG",
                "filled_qty": Decimal("0.01"),
                "avg_entry_price": Decimal("100"),
                "sl_client_algo_id": "sl-single-claim",
                "tp_client_algo_id": "tp-single-claim",
                "sl_status": "SUBMITTED",
                "tp_status": "SUBMITTED",
                "protection_status": "PROTECTED",
            }
        ],
        protection_reconciliation_by_exit_key={
            "exit-key-single-claim": {
                "protection_state": "PROTECTED",
                "sl_classification": "ACTIVE_EVIDENCE_PRESENT",
                "tp_classification": "ACTIVE_EVIDENCE_PRESENT",
                "protection_unknown": False,
            }
        },
        sl_stop_price_by_exit_key={"exit-key-single-claim": Decimal("90")},
        fetch_current_price=lambda symbol, market: Decimal("111"),
        owner_id="worker-single-claim",
        claim_transition=fake_claim,
        run_replacement=fake_replace,
    )

    claim_calls = [call for call in calls if call[0] == "claim"]
    replace_calls = [call for call in calls if call[0] == "replace"]

    assert result == [
        {
            "exit_key": "exit-key-single-claim",
            "result": {"status": "replaced"},
        }
    ]
    assert len(claim_calls) == 1
    assert len(replace_calls) == 1

def test_batch_runner_persists_unknown_quarantine_after_pending_cleanup():
    from decimal import Decimal
    from apps.worker.app.engine.binance_protected_position_batch_reevaluation_runner import (
        reevaluate_active_protected_positions_once,
    )

    calls = []

    protected_position = {
        "exit_key": "exit-key-pending-cleanup-quarantine",
        "symbol": "BTCUSDT",
        "market": "FUTURES",
        "direction": "LONG",
        "filled_qty": Decimal("0.01"),
        "avg_entry_price": Decimal("100"),
        "sl_client_algo_id": "sl-pending-cleanup-quarantine-old",
        "tp_client_algo_id": "tp-pending-cleanup-quarantine",
        "sl_status": "SUBMITTED",
        "tp_status": "SUBMITTED",
        "protection_status": "PROTECTED",
    }

    def fake_claim(**kwargs):
        calls.append(("claim", kwargs))
        return {"status": "claimed"}

    def fake_complete(**kwargs):
        calls.append(("complete", kwargs))
        return {"status": kwargs["final_status"]}

    def fake_persist_reconciliation(**kwargs):
        calls.append(("persist_reconciliation", kwargs))
        return {"status": "updated", "exit_key": kwargs["exit_key"]}

    def fake_replace(**kwargs):
        calls.append(("replace", kwargs))
        return {
            "status": "replacement_pending_cleanup",
            "reason": "old_sl_cancel_failed",
            "old_sl_client_algo_id": "sl-pending-cleanup-quarantine-old",
            "new_sl_client_algo_id": "sl-pending-cleanup-quarantine-new",
        }

    result = reevaluate_active_protected_positions_once(
        protected_positions=[protected_position],
        protection_reconciliation_by_exit_key={
            "exit-key-pending-cleanup-quarantine": {
                "protection_state": "PROTECTED",
                "sl_classification": "ACTIVE_EVIDENCE_PRESENT",
                "tp_classification": "ACTIVE_EVIDENCE_PRESENT",
                "protection_unknown": False,
            }
        },
        sl_stop_price_by_exit_key={
            "exit-key-pending-cleanup-quarantine": Decimal("90")
        },
        fetch_current_price=lambda symbol, market: Decimal("111"),
        owner_id="worker-pending-cleanup-quarantine",
        claim_transition=fake_claim,
        complete_transition=fake_complete,
        persist_reconciliation=fake_persist_reconciliation,
        run_replacement=fake_replace,
    )

    assert result == [
        {
            "exit_key": "exit-key-pending-cleanup-quarantine",
            "result": {
                "status": "replacement_pending_cleanup",
                "reason": "old_sl_cancel_failed",
                "old_sl_client_algo_id": "sl-pending-cleanup-quarantine-old",
                "new_sl_client_algo_id": "sl-pending-cleanup-quarantine-new",
            },
        }
    ]

    assert ("persist_reconciliation", {
        "exit_key": "exit-key-pending-cleanup-quarantine",
        "sl_status": "UNKNOWN",
        "tp_status": "SUBMITTED",
        "protection_status": "UNKNOWN",
        "last_error": "replacement_pending_cleanup:old_sl_cancel_failed",
        "increment_attempt_count": True,
    }) in calls

    complete_calls = [call for call in calls if call[0] == "complete"]
    assert complete_calls[-1] == (
        "complete",
        {
            "exit_key": "exit-key-pending-cleanup-quarantine",
            "required_action": "ACTION_ACTIVATE_TRAILING",
            "owner_id": "worker-pending-cleanup-quarantine",
            "final_status": "ABANDONED",
        },
    )
