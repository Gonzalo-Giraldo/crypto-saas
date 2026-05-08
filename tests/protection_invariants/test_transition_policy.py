from dataclasses import FrozenInstanceError

import pytest

from apps.protection.constants import (
    REASON_INVALID_CURRENT_STATE,
    REASON_PROTECTION_NOT_VERIFIABLE,
    REASON_OK,
    STATE_AUTHORITATIVE_ACTIVE,
    STATE_AUTHORITATIVE_ACTIVE_EQUIVALENT,
    STATE_AUTHORITATIVE_REPLACEMENT_PENDING,
    STATE_PROVISIONAL_ACTIVE,
    STATE_PROVISIONAL_CLEANUP_PENDING,
    STATE_TRAILING_READY,
)

from apps.protection.decision_trace import (
    LifecycleDecisionTrace,
    LifecycleDecisionTraceStep,
)
from apps.protection.evidence_snapshot import ProtectionEvidenceSnapshot
from apps.protection.lifecycle_trace_engine import trace_lifecycle_from_snapshot
from apps.protection.protection_decision import ProtectionDecision
from apps.protection.transition_policy import (
    TransitionPolicyResult,
    authorize_traced_transition,
)


def snapshot(
    *,
    current_state: str,
    correction_required: bool = False,
    baseline_stable: bool = True,
) -> ProtectionEvidenceSnapshot:
    return ProtectionEvidenceSnapshot(
        current_state=current_state,
        reconciliation_status="matched",
        safe_for_position_update=True,
        correction_required=correction_required,
        provisional_sl_active=True,
        provisional_tp_active=True,
        authoritative_sl_active=True,
        authoritative_tp_active=True,
        active_protection_verifiable=True,
        replacement_not_started=True,
        cleanup_successful=True,
        stale_provisional_present=False,
        cleanup_retry_allowed=True,
        baseline_stable=baseline_stable,
        trailing_not_active=True,
    )


def test_policy_authorizes_valid_traced_equivalent_transition():
    trace = trace_lifecycle_from_snapshot(
        snapshot(
            current_state=STATE_PROVISIONAL_ACTIVE,
            correction_required=False,
        )
    )

    result = authorize_traced_transition(trace)

    assert result.allowed is True
    assert result.decision.next_state == STATE_AUTHORITATIVE_ACTIVE_EQUIVALENT


def test_policy_authorizes_valid_traced_replacement_transition():
    trace = trace_lifecycle_from_snapshot(
        snapshot(
            current_state=STATE_PROVISIONAL_ACTIVE,
            correction_required=True,
        )
    )

    result = authorize_traced_transition(trace)

    assert result.allowed is True
    assert result.decision.next_state == STATE_AUTHORITATIVE_REPLACEMENT_PENDING


def test_policy_rejects_denied_trace():
    trace = trace_lifecycle_from_snapshot(
        snapshot(
            current_state=STATE_AUTHORITATIVE_ACTIVE,
            baseline_stable=False,
        )
    )

    result = authorize_traced_transition(trace)

    assert result.allowed is False
    assert result.reason != REASON_OK
    assert result.decision.next_state is None


def test_policy_rejects_allowed_decision_without_next_state():
    allowed_without_next_state = ProtectionDecision(
        allowed=True,
        reason=REASON_OK,
        current_state=STATE_PROVISIONAL_ACTIVE,
        next_state=None,
    )

    trace = LifecycleDecisionTrace(
        current_state=STATE_PROVISIONAL_ACTIVE,
        evaluated_steps=(
            LifecycleDecisionTraceStep(
                evaluator_name="synthetic_invalid_step",
                decision=allowed_without_next_state,
            ),
        ),
        final_decision=allowed_without_next_state,
    )

    result = authorize_traced_transition(trace)

    assert result.allowed is False
    assert result.reason == REASON_INVALID_CURRENT_STATE
    assert result.decision.next_state is None


def test_policy_rejects_transition_not_in_registry():
    forbidden_decision = ProtectionDecision(
        allowed=True,
        reason=REASON_OK,
        current_state=STATE_PROVISIONAL_ACTIVE,
        next_state=STATE_PROVISIONAL_CLEANUP_PENDING,
    )

    trace = LifecycleDecisionTrace(
        current_state=STATE_PROVISIONAL_ACTIVE,
        evaluated_steps=(
            LifecycleDecisionTraceStep(
                evaluator_name="synthetic_forbidden_step",
                decision=forbidden_decision,
            ),
        ),
        final_decision=forbidden_decision,
    )

    result = authorize_traced_transition(trace)

    assert result.allowed is False
    assert result.reason == REASON_INVALID_CURRENT_STATE
    assert result.decision.next_state is None


def test_policy_rejects_allowed_final_decision_without_accepted_step():
    allowed_decision = ProtectionDecision(
        allowed=True,
        reason=REASON_OK,
        current_state=STATE_AUTHORITATIVE_ACTIVE,
        next_state=STATE_TRAILING_READY,
    )

    rejected_step = ProtectionDecision(
        allowed=False,
        reason=REASON_INVALID_CURRENT_STATE,
        current_state=STATE_AUTHORITATIVE_ACTIVE,
        next_state=None,
    )

    trace = LifecycleDecisionTrace(
        current_state=STATE_AUTHORITATIVE_ACTIVE,
        evaluated_steps=(
            LifecycleDecisionTraceStep(
                evaluator_name="synthetic_rejected_step",
                decision=rejected_step,
            ),
        ),
        final_decision=allowed_decision,
    )

    result = authorize_traced_transition(trace)

    assert result.allowed is False
    assert result.reason == REASON_INVALID_CURRENT_STATE
    assert result.decision.next_state is None


def test_policy_rejects_final_decision_mismatch_with_accepted_step():
    accepted_step_decision = ProtectionDecision(
        allowed=True,
        reason=REASON_OK,
        current_state=STATE_AUTHORITATIVE_ACTIVE,
        next_state=STATE_TRAILING_READY,
    )

    mismatched_final_decision = ProtectionDecision(
        allowed=True,
        reason=REASON_OK,
        current_state=STATE_AUTHORITATIVE_ACTIVE_EQUIVALENT,
        next_state=STATE_TRAILING_READY,
    )

    trace = LifecycleDecisionTrace(
        current_state=STATE_AUTHORITATIVE_ACTIVE,
        evaluated_steps=(
            LifecycleDecisionTraceStep(
                evaluator_name="synthetic_accepted_step",
                decision=accepted_step_decision,
            ),
        ),
        final_decision=mismatched_final_decision,
    )

    result = authorize_traced_transition(trace)

    assert result.allowed is False
    assert result.reason == REASON_PROTECTION_NOT_VERIFIABLE
    assert result.decision.next_state is None


def test_transition_policy_result_is_immutable():
    trace = trace_lifecycle_from_snapshot(
        snapshot(
            current_state=STATE_PROVISIONAL_ACTIVE,
            correction_required=False,
        )
    )

    result = authorize_traced_transition(trace)

    with pytest.raises(FrozenInstanceError):
        result.allowed = False


def test_transition_policy_result_type_is_explicit():
    trace = trace_lifecycle_from_snapshot(
        snapshot(
            current_state=STATE_PROVISIONAL_ACTIVE,
            correction_required=False,
        )
    )

    result = authorize_traced_transition(trace)

    assert isinstance(result, TransitionPolicyResult)
