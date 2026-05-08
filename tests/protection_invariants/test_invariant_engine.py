from dataclasses import FrozenInstanceError

import pytest

from apps.protection.constants import (
    REASON_INVALID_CURRENT_STATE,
    REASON_OK,
    REASON_PROTECTION_NOT_VERIFIABLE,
    STATE_AUTHORITATIVE_ACTIVE,
    STATE_PROVISIONAL_ACTIVE,
    STATE_PROVISIONAL_CLEANUP_PENDING,
)

from apps.protection.evidence_snapshot import (
    ProtectionEvidenceSnapshot,
)
from apps.protection.invariant_engine import (
    InvariantResult,
    LifecycleInvariantEvaluation,
    evaluate_lifecycle_invariants,
)
from apps.protection.lifecycle_trace_engine import (
    trace_lifecycle_from_snapshot,
)
from apps.protection.transition_policy import (
    authorize_traced_transition,
)


def snapshot(
    *,
    current_state: str,
    reconciliation_status: str = "matched",
    cleanup_successful: bool = True,
    stale_provisional_present: bool = False,
    baseline_stable: bool = True,
) -> ProtectionEvidenceSnapshot:
    return ProtectionEvidenceSnapshot(
        current_state=current_state,
        reconciliation_status=reconciliation_status,
        safe_for_position_update=True,
        correction_required=False,
        provisional_sl_active=True,
        provisional_tp_active=True,
        authoritative_sl_active=True,
        authoritative_tp_active=True,
        active_protection_verifiable=True,
        replacement_not_started=True,
        cleanup_successful=cleanup_successful,
        stale_provisional_present=stale_provisional_present,
        cleanup_retry_allowed=True,
        baseline_stable=baseline_stable,
        trailing_not_active=True,
    )


def evaluate(snapshot_input: ProtectionEvidenceSnapshot):
    trace = trace_lifecycle_from_snapshot(snapshot_input)

    policy_result = authorize_traced_transition(trace)

    return evaluate_lifecycle_invariants(
        snapshot=snapshot_input,
        policy_result=policy_result,
    )


def test_invariant_engine_accepts_valid_equivalent_path():
    result = evaluate(
        snapshot(
            current_state=STATE_PROVISIONAL_ACTIVE,
            reconciliation_status="matched",
        )
    )

    assert result.allowed is True


def test_invariant_engine_rejects_unmatched_reconciliation():
    result = evaluate(
        snapshot(
            current_state=STATE_PROVISIONAL_ACTIVE,
            reconciliation_status="unmatched",
        )
    )

    assert result.allowed is False

    failed = [
        item
        for item in result.invariant_results
        if not item.valid
    ]

    assert failed[0].reason != REASON_OK


def test_invariant_engine_rejects_unstable_trailing_baseline():
    result = evaluate(
        snapshot(
            current_state=STATE_AUTHORITATIVE_ACTIVE,
            baseline_stable=False,
        )
    )

    assert result.allowed is False

    failed = [
        item
        for item in result.invariant_results
        if not item.valid
    ]

    assert failed[0].reason != REASON_OK


def test_cleanup_failure_requires_stale_protection_presence():
    result = evaluate(
        snapshot(
            current_state=STATE_PROVISIONAL_CLEANUP_PENDING,
            cleanup_successful=False,
            stale_provisional_present=False,
        )
    )

    assert result.allowed is False

    failed = [
        item
        for item in result.invariant_results
        if not item.valid
    ]

    assert failed[0].reason != REASON_OK


def test_invariant_engine_returns_explicit_result_type():
    result = evaluate(
        snapshot(
            current_state=STATE_PROVISIONAL_ACTIVE,
        )
    )

    assert isinstance(
        result,
        LifecycleInvariantEvaluation,
    )


def test_invariant_results_are_explicit_types():
    result = evaluate(
        snapshot(
            current_state=STATE_PROVISIONAL_ACTIVE,
        )
    )

    assert all(
        isinstance(item, InvariantResult)
        for item in result.invariant_results
    )


def test_invariant_engine_is_immutable():
    result = evaluate(
        snapshot(
            current_state=STATE_PROVISIONAL_ACTIVE,
        )
    )

    with pytest.raises(FrozenInstanceError):
        result.allowed = False


def test_valid_invariants_return_reason_ok():
    result = evaluate(
        snapshot(
            current_state=STATE_PROVISIONAL_ACTIVE,
        )
    )

    valid_reasons = {
        item.reason
        for item in result.invariant_results
        if item.valid
    }

    assert REASON_OK in valid_reasons
