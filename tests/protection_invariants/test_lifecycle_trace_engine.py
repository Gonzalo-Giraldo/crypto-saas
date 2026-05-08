from dataclasses import FrozenInstanceError

import pytest

from apps.protection.constants import (
    REASON_INVALID_CURRENT_STATE,
    STATE_AUTHORITATIVE_ACTIVE,
    STATE_AUTHORITATIVE_ACTIVE_EQUIVALENT,
    STATE_AUTHORITATIVE_REPLACEMENT_PENDING,
    STATE_PROVISIONAL_ACTIVE,
    STATE_PROVISIONAL_CLEANUP_PENDING,
    STATE_STALE_PROVISIONAL_PRESENT,
    STATE_TRAILING_READY,
)

from apps.protection.decision_trace import LifecycleDecisionTrace
from apps.protection.evidence_snapshot import ProtectionEvidenceSnapshot
from apps.protection.lifecycle_engine import evaluate_lifecycle_from_snapshot
from apps.protection.lifecycle_trace_engine import (
    trace_lifecycle_from_snapshot,
)


def snapshot(
    *,
    current_state: str,
    correction_required: bool = False,
    cleanup_successful: bool = True,
    stale_provisional_present: bool = False,
    baseline_stable: bool = True,
    active_protection_verifiable: bool = True,
    authoritative_sl_active: bool = True,
    authoritative_tp_active: bool = True,
    provisional_sl_active: bool = True,
    provisional_tp_active: bool = True,
    reconciliation_status: str = "matched",
    safe_for_position_update: bool = True,
    replacement_not_started: bool = True,
    cleanup_retry_allowed: bool = True,
    trailing_not_active: bool = True,
) -> ProtectionEvidenceSnapshot:
    return ProtectionEvidenceSnapshot(
        current_state=current_state,
        reconciliation_status=reconciliation_status,
        safe_for_position_update=safe_for_position_update,
        correction_required=correction_required,
        provisional_sl_active=provisional_sl_active,
        provisional_tp_active=provisional_tp_active,
        authoritative_sl_active=authoritative_sl_active,
        authoritative_tp_active=authoritative_tp_active,
        active_protection_verifiable=active_protection_verifiable,
        replacement_not_started=replacement_not_started,
        cleanup_successful=cleanup_successful,
        stale_provisional_present=stale_provisional_present,
        cleanup_retry_allowed=cleanup_retry_allowed,
        baseline_stable=baseline_stable,
        trailing_not_active=trailing_not_active,
    )


def test_trace_matches_lifecycle_engine_final_decision():
    evidence = snapshot(
        current_state=STATE_PROVISIONAL_ACTIVE,
        correction_required=True,
    )

    trace = trace_lifecycle_from_snapshot(evidence)
    decision = evaluate_lifecycle_from_snapshot(evidence)

    assert trace.final_decision == decision


def test_trace_records_equivalent_path_as_single_accepted_step():
    trace = trace_lifecycle_from_snapshot(
        snapshot(
            current_state=STATE_PROVISIONAL_ACTIVE,
            correction_required=False,
        )
    )

    assert trace.final_decision.allowed is True
    assert trace.final_decision.next_state == STATE_AUTHORITATIVE_ACTIVE_EQUIVALENT
    assert len(trace.evaluated_steps) == 1
    assert len(trace.accepted_steps) == 1
    assert len(trace.rejected_steps) == 0
    assert (
        trace.evaluated_steps[0].evaluator_name
        == "evaluate_equivalent_from_snapshot"
    )


def test_trace_records_rejected_equivalent_before_replacement():
    trace = trace_lifecycle_from_snapshot(
        snapshot(
            current_state=STATE_PROVISIONAL_ACTIVE,
            correction_required=True,
        )
    )

    assert trace.final_decision.allowed is True
    assert trace.final_decision.next_state == STATE_AUTHORITATIVE_REPLACEMENT_PENDING
    assert len(trace.evaluated_steps) == 2
    assert len(trace.rejected_steps) == 1
    assert len(trace.accepted_steps) == 1
    assert (
        trace.evaluated_steps[0].evaluator_name
        == "evaluate_equivalent_from_snapshot"
    )
    assert (
        trace.evaluated_steps[1].evaluator_name
        == "evaluate_replacement_from_snapshot"
    )


def test_trace_records_cleanup_success():
    trace = trace_lifecycle_from_snapshot(
        snapshot(
            current_state=STATE_PROVISIONAL_CLEANUP_PENDING,
            cleanup_successful=True,
            stale_provisional_present=False,
        )
    )

    assert trace.final_decision.allowed is True
    assert trace.final_decision.next_state == STATE_AUTHORITATIVE_ACTIVE
    assert len(trace.evaluated_steps) == 1


def test_trace_records_cleanup_failure_as_stale_not_failure():
    trace = trace_lifecycle_from_snapshot(
        snapshot(
            current_state=STATE_PROVISIONAL_CLEANUP_PENDING,
            cleanup_successful=False,
            stale_provisional_present=True,
        )
    )

    assert trace.final_decision.allowed is True
    assert trace.final_decision.next_state == STATE_STALE_PROVISIONAL_PRESENT
    assert len(trace.accepted_steps) == 1


def test_trace_records_trailing_activation():
    trace = trace_lifecycle_from_snapshot(
        snapshot(
            current_state=STATE_AUTHORITATIVE_ACTIVE,
            baseline_stable=True,
        )
    )

    assert trace.final_decision.allowed is True
    assert trace.final_decision.next_state == STATE_TRAILING_READY
    assert len(trace.evaluated_steps) == 1


def test_trace_rejects_unknown_state_without_evaluated_steps():
    trace = trace_lifecycle_from_snapshot(
        snapshot(
            current_state="UNKNOWN_STATE",
        )
    )

    assert trace.final_decision.allowed is False
    assert trace.final_decision.reason == REASON_INVALID_CURRENT_STATE
    assert trace.final_decision.next_state is None
    assert trace.evaluated_steps == tuple()


def test_trace_is_immutable():
    trace = trace_lifecycle_from_snapshot(
        snapshot(
            current_state=STATE_AUTHORITATIVE_ACTIVE_EQUIVALENT,
        )
    )

    with pytest.raises(FrozenInstanceError):
        trace.current_state = "MUTATED"


def test_trace_type_is_explicit():
    trace = trace_lifecycle_from_snapshot(
        snapshot(
            current_state=STATE_AUTHORITATIVE_REPLACEMENT_PENDING,
        )
    )

    assert isinstance(trace, LifecycleDecisionTrace)
