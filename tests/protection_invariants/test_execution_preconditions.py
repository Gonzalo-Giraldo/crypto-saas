from dataclasses import FrozenInstanceError

import pytest

from apps.protection.constants import (
    STATE_AUTHORITATIVE_ACTIVE,
    STATE_AUTHORITATIVE_REPLACEMENT_PENDING,
    STATE_PROVISIONAL_ACTIVE,
    STATE_PROVISIONAL_CLEANUP_PENDING,
    STATE_STALE_PROVISIONAL_PRESENT,
)

from apps.protection.evidence_snapshot import ProtectionEvidenceSnapshot
from apps.protection.execution_preconditions import (
    ExecutionPreconditions,
    PRECONDITION_ACTIVE_PROTECTION_VERIFIED,
    PRECONDITION_AUTHORITATIVE_PROTECTION_PRESENT,
    PRECONDITION_BASELINE_STABLE,
    PRECONDITION_CLEANUP_CONFIRMED,
    PRECONDITION_NO_EXECUTION_FOR_DENIED_CONTRACT,
    PRECONDITION_PROVISIONAL_PROTECTION_PRESENT,
    PRECONDITION_RECONCILIATION_MATCHED,
    PRECONDITION_SAFE_FOR_POSITION_UPDATE,
    PRECONDITION_STALE_PROVISIONAL_CONFIRMED,
    PRECONDITION_TRAILING_CONFIRMED,
    PRECONDITION_TRAILING_READY_TO_ACTIVATE,
    build_execution_preconditions,
)
from apps.protection.invariant_engine import evaluate_lifecycle_invariants
from apps.protection.lifecycle_trace_engine import trace_lifecycle_from_snapshot
from apps.protection.runtime_contract import (
    ACTION_ACCEPT_AUTHORITATIVE_EQUIVALENT,
    ACTION_ACTIVATE_TRAILING,
    ACTION_MARK_AUTHORITATIVE_ACTIVE,
    ACTION_MARK_STALE_PROVISIONAL_PRESENT,
    ACTION_NONE,
    ACTION_RETRY_PROVISIONAL_CLEANUP,
    ACTION_START_AUTHORITATIVE_REPLACEMENT,
    ACTION_START_PROVISIONAL_CLEANUP,
    build_runtime_contract,
)
from apps.protection.runtime_evidence_requirements import (
    build_runtime_evidence_requirements,
)
from apps.protection.transition_policy import authorize_traced_transition


def snapshot(
    *,
    current_state: str,
    correction_required: bool = False,
    cleanup_successful: bool = True,
    stale_provisional_present: bool = False,
    baseline_stable: bool = True,
    reconciliation_status: str = "matched",
) -> ProtectionEvidenceSnapshot:
    return ProtectionEvidenceSnapshot(
        current_state=current_state,
        reconciliation_status=reconciliation_status,
        safe_for_position_update=True,
        correction_required=correction_required,
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


def preconditions_for(snapshot_input: ProtectionEvidenceSnapshot):
    trace = trace_lifecycle_from_snapshot(snapshot_input)
    policy = authorize_traced_transition(trace)
    invariants = evaluate_lifecycle_invariants(
        snapshot=snapshot_input,
        policy_result=policy,
    )
    contract = build_runtime_contract(invariants)
    requirements = build_runtime_evidence_requirements(contract)

    return build_execution_preconditions(requirements)


def test_equivalent_acceptance_requires_safe_provisional_preconditions():
    preconditions = preconditions_for(
        snapshot(
            current_state=STATE_PROVISIONAL_ACTIVE,
            correction_required=False,
        )
    )

    assert preconditions.allowed is True
    assert preconditions.required_action == ACTION_ACCEPT_AUTHORITATIVE_EQUIVALENT
    assert preconditions.required_preconditions == (
        PRECONDITION_ACTIVE_PROTECTION_VERIFIED,
        PRECONDITION_RECONCILIATION_MATCHED,
        PRECONDITION_SAFE_FOR_POSITION_UPDATE,
        PRECONDITION_PROVISIONAL_PROTECTION_PRESENT,
    )


def test_replacement_requires_safe_provisional_preconditions():
    preconditions = preconditions_for(
        snapshot(
            current_state=STATE_PROVISIONAL_ACTIVE,
            correction_required=True,
        )
    )

    assert preconditions.allowed is True
    assert preconditions.required_action == ACTION_START_AUTHORITATIVE_REPLACEMENT
    assert PRECONDITION_ACTIVE_PROTECTION_VERIFIED in (
        preconditions.required_preconditions
    )
    assert PRECONDITION_PROVISIONAL_PROTECTION_PRESENT in (
        preconditions.required_preconditions
    )


def test_cleanup_start_requires_authoritative_protection_present():
    preconditions = preconditions_for(
        snapshot(
            current_state=STATE_AUTHORITATIVE_REPLACEMENT_PENDING,
        )
    )

    assert preconditions.allowed is True
    assert preconditions.required_action == ACTION_START_PROVISIONAL_CLEANUP
    assert preconditions.required_preconditions == (
        PRECONDITION_ACTIVE_PROTECTION_VERIFIED,
        PRECONDITION_AUTHORITATIVE_PROTECTION_PRESENT,
    )


def test_authoritative_active_requires_cleanup_confirmation():
    preconditions = preconditions_for(
        snapshot(
            current_state=STATE_PROVISIONAL_CLEANUP_PENDING,
            cleanup_successful=True,
            stale_provisional_present=False,
        )
    )

    assert preconditions.allowed is True
    assert preconditions.required_action == ACTION_MARK_AUTHORITATIVE_ACTIVE
    assert PRECONDITION_CLEANUP_CONFIRMED in (
        preconditions.required_preconditions
    )


def test_stale_provisional_requires_stale_confirmation():
    preconditions = preconditions_for(
        snapshot(
            current_state=STATE_PROVISIONAL_CLEANUP_PENDING,
            cleanup_successful=False,
            stale_provisional_present=True,
        )
    )

    assert preconditions.allowed is True
    assert preconditions.required_action == ACTION_MARK_STALE_PROVISIONAL_PRESENT
    assert PRECONDITION_STALE_PROVISIONAL_CONFIRMED in (
        preconditions.required_preconditions
    )


def test_retry_cleanup_requires_stale_and_authoritative_preconditions():
    preconditions = preconditions_for(
        snapshot(
            current_state=STATE_STALE_PROVISIONAL_PRESENT,
            stale_provisional_present=True,
        )
    )

    assert preconditions.allowed is True
    assert preconditions.required_action == ACTION_RETRY_PROVISIONAL_CLEANUP
    assert PRECONDITION_AUTHORITATIVE_PROTECTION_PRESENT in (
        preconditions.required_preconditions
    )
    assert PRECONDITION_STALE_PROVISIONAL_CONFIRMED in (
        preconditions.required_preconditions
    )


def test_trailing_requires_baseline_and_trailing_preconditions():
    preconditions = preconditions_for(
        snapshot(
            current_state=STATE_AUTHORITATIVE_ACTIVE,
            baseline_stable=True,
        )
    )

    assert preconditions.allowed is True
    assert preconditions.required_action == ACTION_ACTIVATE_TRAILING
    assert preconditions.required_preconditions == (
        PRECONDITION_ACTIVE_PROTECTION_VERIFIED,
        PRECONDITION_AUTHORITATIVE_PROTECTION_PRESENT,
        PRECONDITION_BASELINE_STABLE,
        PRECONDITION_TRAILING_READY_TO_ACTIVATE,
        PRECONDITION_TRAILING_CONFIRMED,
    )


def test_denied_contract_has_no_execution_preconditions_except_denial():
    preconditions = preconditions_for(
        snapshot(
            current_state=STATE_PROVISIONAL_ACTIVE,
            reconciliation_status="unmatched",
        )
    )

    assert preconditions.allowed is False
    assert preconditions.required_action == ACTION_NONE
    assert preconditions.required_preconditions == (
        PRECONDITION_NO_EXECUTION_FOR_DENIED_CONTRACT,
    )


def test_execution_preconditions_are_immutable():
    preconditions = preconditions_for(
        snapshot(
            current_state=STATE_PROVISIONAL_ACTIVE,
            correction_required=False,
        )
    )

    with pytest.raises(FrozenInstanceError):
        preconditions.allowed = False


def test_execution_preconditions_type_is_explicit():
    preconditions = preconditions_for(
        snapshot(
            current_state=STATE_PROVISIONAL_ACTIVE,
            correction_required=False,
        )
    )

    assert isinstance(preconditions, ExecutionPreconditions)
