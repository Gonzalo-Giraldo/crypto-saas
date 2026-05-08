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
    EVIDENCE_ACTIVE_PROTECTION_VERIFIABLE,
    EVIDENCE_AUTHORITATIVE_SL_ACTIVE,
    EVIDENCE_AUTHORITATIVE_TP_ACTIVE,
    EVIDENCE_BASELINE_STABLE,
    EVIDENCE_CLEANUP_CONFIRMED,
    EVIDENCE_PROVISIONAL_SL_ACTIVE,
    EVIDENCE_PROVISIONAL_TP_ACTIVE,
    EVIDENCE_RECONCILIATION_MATCHED,
    EVIDENCE_SAFE_FOR_POSITION_UPDATE,
    EVIDENCE_STALE_PROVISIONAL_CONFIRMED,
    EVIDENCE_TRAILING_CONFIRMED,
    EVIDENCE_TRAILING_NOT_ACTIVE,
    RuntimeEvidenceRequirements,
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


def requirements_for(snapshot_input: ProtectionEvidenceSnapshot):
    trace = trace_lifecycle_from_snapshot(snapshot_input)
    policy = authorize_traced_transition(trace)
    invariants = evaluate_lifecycle_invariants(
        snapshot=snapshot_input,
        policy_result=policy,
    )
    contract = build_runtime_contract(invariants)

    return build_runtime_evidence_requirements(contract)


def test_equivalent_acceptance_requires_provisional_and_reconciliation_evidence():
    requirements = requirements_for(
        snapshot(
            current_state=STATE_PROVISIONAL_ACTIVE,
            correction_required=False,
        )
    )

    assert requirements.allowed is True
    assert requirements.required_action == ACTION_ACCEPT_AUTHORITATIVE_EQUIVALENT
    assert requirements.required_evidence == (
        EVIDENCE_PROVISIONAL_SL_ACTIVE,
        EVIDENCE_PROVISIONAL_TP_ACTIVE,
        EVIDENCE_ACTIVE_PROTECTION_VERIFIABLE,
        EVIDENCE_RECONCILIATION_MATCHED,
        EVIDENCE_SAFE_FOR_POSITION_UPDATE,
    )


def test_replacement_requires_provisional_and_reconciliation_evidence():
    requirements = requirements_for(
        snapshot(
            current_state=STATE_PROVISIONAL_ACTIVE,
            correction_required=True,
        )
    )

    assert requirements.allowed is True
    assert requirements.required_action == ACTION_START_AUTHORITATIVE_REPLACEMENT
    assert EVIDENCE_PROVISIONAL_SL_ACTIVE in requirements.required_evidence
    assert EVIDENCE_PROVISIONAL_TP_ACTIVE in requirements.required_evidence
    assert EVIDENCE_RECONCILIATION_MATCHED in requirements.required_evidence


def test_cleanup_start_requires_authoritative_evidence():
    requirements = requirements_for(
        snapshot(
            current_state=STATE_AUTHORITATIVE_REPLACEMENT_PENDING,
        )
    )

    assert requirements.allowed is True
    assert requirements.required_action == ACTION_START_PROVISIONAL_CLEANUP
    assert requirements.required_evidence == (
        EVIDENCE_AUTHORITATIVE_SL_ACTIVE,
        EVIDENCE_AUTHORITATIVE_TP_ACTIVE,
        EVIDENCE_ACTIVE_PROTECTION_VERIFIABLE,
    )


def test_authoritative_active_requires_cleanup_confirmation():
    requirements = requirements_for(
        snapshot(
            current_state=STATE_PROVISIONAL_CLEANUP_PENDING,
            cleanup_successful=True,
            stale_provisional_present=False,
        )
    )

    assert requirements.allowed is True
    assert requirements.required_action == ACTION_MARK_AUTHORITATIVE_ACTIVE
    assert EVIDENCE_CLEANUP_CONFIRMED in requirements.required_evidence


def test_stale_provisional_requires_stale_confirmation():
    requirements = requirements_for(
        snapshot(
            current_state=STATE_PROVISIONAL_CLEANUP_PENDING,
            cleanup_successful=False,
            stale_provisional_present=True,
        )
    )

    assert requirements.allowed is True
    assert requirements.required_action == ACTION_MARK_STALE_PROVISIONAL_PRESENT
    assert EVIDENCE_STALE_PROVISIONAL_CONFIRMED in requirements.required_evidence


def test_retry_cleanup_requires_authoritative_and_stale_evidence():
    requirements = requirements_for(
        snapshot(
            current_state=STATE_STALE_PROVISIONAL_PRESENT,
            stale_provisional_present=True,
        )
    )

    assert requirements.allowed is True
    assert requirements.required_action == ACTION_RETRY_PROVISIONAL_CLEANUP
    assert EVIDENCE_AUTHORITATIVE_SL_ACTIVE in requirements.required_evidence
    assert EVIDENCE_AUTHORITATIVE_TP_ACTIVE in requirements.required_evidence
    assert EVIDENCE_STALE_PROVISIONAL_CONFIRMED in requirements.required_evidence


def test_trailing_requires_authoritative_baseline_and_trailing_evidence():
    requirements = requirements_for(
        snapshot(
            current_state=STATE_AUTHORITATIVE_ACTIVE,
            baseline_stable=True,
        )
    )

    assert requirements.allowed is True
    assert requirements.required_action == ACTION_ACTIVATE_TRAILING
    assert requirements.required_evidence == (
        EVIDENCE_AUTHORITATIVE_SL_ACTIVE,
        EVIDENCE_AUTHORITATIVE_TP_ACTIVE,
        EVIDENCE_ACTIVE_PROTECTION_VERIFIABLE,
        EVIDENCE_BASELINE_STABLE,
        EVIDENCE_TRAILING_NOT_ACTIVE,
        EVIDENCE_TRAILING_CONFIRMED,
    )


def test_denied_contract_has_no_required_runtime_evidence():
    requirements = requirements_for(
        snapshot(
            current_state=STATE_PROVISIONAL_ACTIVE,
            reconciliation_status="unmatched",
        )
    )

    assert requirements.allowed is False
    assert requirements.required_action == ACTION_NONE
    assert requirements.required_evidence == tuple()


def test_runtime_evidence_requirements_are_immutable():
    requirements = requirements_for(
        snapshot(
            current_state=STATE_PROVISIONAL_ACTIVE,
            correction_required=False,
        )
    )

    with pytest.raises(FrozenInstanceError):
        requirements.allowed = False


def test_runtime_evidence_requirements_type_is_explicit():
    requirements = requirements_for(
        snapshot(
            current_state=STATE_PROVISIONAL_ACTIVE,
            correction_required=False,
        )
    )

    assert isinstance(requirements, RuntimeEvidenceRequirements)
