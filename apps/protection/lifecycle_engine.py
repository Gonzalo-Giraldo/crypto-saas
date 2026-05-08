from apps.protection.constants import (
    REASON_INVALID_CURRENT_STATE,
    STATE_AUTHORITATIVE_ACTIVE,
    STATE_AUTHORITATIVE_ACTIVE_EQUIVALENT,
    STATE_AUTHORITATIVE_REPLACEMENT_PENDING,
    STATE_PROVISIONAL_ACTIVE,
    STATE_PROVISIONAL_CLEANUP_PENDING,
    STATE_STALE_PROVISIONAL_PRESENT,
)

from apps.protection.evidence_snapshot import ProtectionEvidenceSnapshot
from apps.protection.protection_decision import ProtectionDecision
from apps.protection.snapshot_evaluators import (
    evaluate_cleanup_result_from_snapshot,
    evaluate_cleanup_retry_from_snapshot,
    evaluate_cleanup_start_from_snapshot,
    evaluate_equivalent_from_snapshot,
    evaluate_replacement_from_snapshot,
    evaluate_trailing_from_snapshot,
)
from apps.protection.transition_assertions import assert_allowed_transition


def evaluate_lifecycle_from_snapshot(
    snapshot: ProtectionEvidenceSnapshot,
) -> ProtectionDecision:
    if snapshot.current_state == STATE_PROVISIONAL_ACTIVE:
        equivalent_decision = evaluate_equivalent_from_snapshot(snapshot)

        if equivalent_decision.allowed:
            return assert_allowed_transition(
                current_state=equivalent_decision.current_state,
                next_state=equivalent_decision.next_state,
            )

        replacement_decision = evaluate_replacement_from_snapshot(snapshot)

        if replacement_decision.allowed:
            return assert_allowed_transition(
                current_state=replacement_decision.current_state,
                next_state=replacement_decision.next_state,
            )

        return replacement_decision

    if snapshot.current_state == STATE_AUTHORITATIVE_REPLACEMENT_PENDING:
        cleanup_start_decision = evaluate_cleanup_start_from_snapshot(snapshot)

        if cleanup_start_decision.allowed:
            return assert_allowed_transition(
                current_state=cleanup_start_decision.current_state,
                next_state=cleanup_start_decision.next_state,
            )

        return cleanup_start_decision

    if snapshot.current_state == STATE_PROVISIONAL_CLEANUP_PENDING:
        cleanup_result_decision = evaluate_cleanup_result_from_snapshot(snapshot)

        if cleanup_result_decision.allowed:
            return assert_allowed_transition(
                current_state=cleanup_result_decision.current_state,
                next_state=cleanup_result_decision.next_state,
            )

        return cleanup_result_decision

    if snapshot.current_state == STATE_STALE_PROVISIONAL_PRESENT:
        cleanup_retry_decision = evaluate_cleanup_retry_from_snapshot(snapshot)

        if cleanup_retry_decision.allowed:
            return assert_allowed_transition(
                current_state=cleanup_retry_decision.current_state,
                next_state=cleanup_retry_decision.next_state,
            )

        return cleanup_retry_decision

    if snapshot.current_state in {
        STATE_AUTHORITATIVE_ACTIVE,
        STATE_AUTHORITATIVE_ACTIVE_EQUIVALENT,
    }:
        trailing_decision = evaluate_trailing_from_snapshot(snapshot)

        if trailing_decision.allowed:
            return assert_allowed_transition(
                current_state=trailing_decision.current_state,
                next_state=trailing_decision.next_state,
            )

        return trailing_decision

    return ProtectionDecision(
        allowed=False,
        reason=REASON_INVALID_CURRENT_STATE,
        current_state=snapshot.current_state,
        next_state=None,
    )
