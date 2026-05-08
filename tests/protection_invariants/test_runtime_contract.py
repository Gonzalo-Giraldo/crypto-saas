from dataclasses import FrozenInstanceError

import pytest

from apps.protection.constants import (
    STATE_AUTHORITATIVE_ACTIVE,
    STATE_AUTHORITATIVE_REPLACEMENT_PENDING,
    STATE_PROVISIONAL_ACTIVE,
    STATE_PROVISIONAL_CLEANUP_PENDING,
    STATE_STALE_PROVISIONAL_PRESENT,
    STATE_TRAILING_READY,
)

from apps.protection.evidence_snapshot import ProtectionEvidenceSnapshot
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
    ProtectionRuntimeContract,
    build_runtime_contract,
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


def contract_for(snapshot_input: ProtectionEvidenceSnapshot):
    trace = trace_lifecycle_from_snapshot(snapshot_input)
    policy = authorize_traced_transition(trace)
    invariants = evaluate_lifecycle_invariants(
        snapshot=snapshot_input,
        policy_result=policy,
    )

    return build_runtime_contract(invariants)


def test_contract_accepts_authoritative_equivalent_without_cleanup():
    contract = contract_for(
        snapshot(
            current_state=STATE_PROVISIONAL_ACTIVE,
            correction_required=False,
        )
    )

    assert contract.allowed is True
    assert contract.required_action == ACTION_ACCEPT_AUTHORITATIVE_EQUIVALENT
    assert contract.requires_authoritative_confirmation is True
    assert contract.requires_cleanup_confirmation is False
    assert contract.requires_trailing_confirmation is False


def test_contract_starts_authoritative_replacement_without_cleanup():
    contract = contract_for(
        snapshot(
            current_state=STATE_PROVISIONAL_ACTIVE,
            correction_required=True,
        )
    )

    assert contract.allowed is True
    assert contract.required_action == ACTION_START_AUTHORITATIVE_REPLACEMENT
    assert contract.requires_authoritative_confirmation is True
    assert contract.requires_cleanup_confirmation is False


def test_contract_starts_cleanup_after_authoritative_pending():
    contract = contract_for(
        snapshot(
            current_state=STATE_AUTHORITATIVE_REPLACEMENT_PENDING,
        )
    )

    assert contract.allowed is True
    assert contract.required_action == ACTION_START_PROVISIONAL_CLEANUP
    assert contract.requires_authoritative_confirmation is True
    assert contract.requires_cleanup_confirmation is True


def test_contract_marks_authoritative_active_after_cleanup_success():
    contract = contract_for(
        snapshot(
            current_state=STATE_PROVISIONAL_CLEANUP_PENDING,
            cleanup_successful=True,
            stale_provisional_present=False,
        )
    )

    assert contract.allowed is True
    assert contract.required_action == ACTION_MARK_AUTHORITATIVE_ACTIVE
    assert contract.next_state == STATE_AUTHORITATIVE_ACTIVE


def test_contract_marks_stale_provisional_without_failure():
    contract = contract_for(
        snapshot(
            current_state=STATE_PROVISIONAL_CLEANUP_PENDING,
            cleanup_successful=False,
            stale_provisional_present=True,
        )
    )

    assert contract.allowed is True
    assert contract.required_action == ACTION_MARK_STALE_PROVISIONAL_PRESENT
    assert contract.next_state == STATE_STALE_PROVISIONAL_PRESENT


def test_contract_retries_cleanup_only_from_stale_state():
    contract = contract_for(
        snapshot(
            current_state=STATE_STALE_PROVISIONAL_PRESENT,
            stale_provisional_present=True,
        )
    )

    assert contract.allowed is True
    assert contract.required_action == ACTION_RETRY_PROVISIONAL_CLEANUP
    assert contract.requires_cleanup_confirmation is True


def test_contract_activates_trailing_with_trailing_confirmation():
    contract = contract_for(
        snapshot(
            current_state=STATE_AUTHORITATIVE_ACTIVE,
            baseline_stable=True,
        )
    )

    assert contract.allowed is True
    assert contract.required_action == ACTION_ACTIVATE_TRAILING
    assert contract.next_state == STATE_TRAILING_READY
    assert contract.requires_trailing_confirmation is True


def test_contract_denies_invalid_invariant_result_with_no_action():
    contract = contract_for(
        snapshot(
            current_state=STATE_PROVISIONAL_ACTIVE,
            reconciliation_status="unmatched",
        )
    )

    assert contract.allowed is False
    assert contract.required_action == ACTION_NONE
    assert contract.next_state is None


def test_runtime_contract_is_immutable():
    contract = contract_for(
        snapshot(
            current_state=STATE_PROVISIONAL_ACTIVE,
            correction_required=False,
        )
    )

    with pytest.raises(FrozenInstanceError):
        contract.allowed = False


def test_runtime_contract_type_is_explicit():
    contract = contract_for(
        snapshot(
            current_state=STATE_PROVISIONAL_ACTIVE,
            correction_required=False,
        )
    )

    assert isinstance(contract, ProtectionRuntimeContract)
